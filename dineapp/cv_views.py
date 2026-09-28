"""
CV Views — All views and API endpoints for the occupancy detection system.
Handles dashboard rendering, zone calibration, video upload, pipeline control, and REST APIs.
"""

import os
import json
import time
import threading
import logging
import base64
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings

from .models import Restaurant
from .cv_models import CameraFeed, TableZone, OccupancySnapshot, OccupancyAnalytics

logger = logging.getLogger(__name__)

# ─── Global Pipeline State ───────────────────────────────────────────────────
# In production, use Celery or a proper task queue. For demo, a global dict suffices.
_active_pipelines = {}  # {restaurant_id: OccupancyPipeline}
_pipeline_lock = threading.Lock()


def _get_pipeline(restaurant_id):
    """Get active pipeline for a restaurant, if any."""
    return _active_pipelines.get(restaurant_id)


# ─── Dashboard View ─────────────────────────────────────────────────────────

@login_required(login_url='restaurantlogin')
def occupancy_dashboard(request):
    """Render the main occupancy monitoring dashboard."""
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
    except Restaurant.DoesNotExist:
        return redirect('restaurantlogin')

    cameras = CameraFeed.objects.filter(restaurant=restaurant)
    zones = TableZone.objects.filter(restaurant=restaurant)

    # Current occupancy stats
    total = zones.count()
    occupied = zones.filter(status='occupied').count()
    cooldown = zones.filter(status='cooldown').count()
    available = total - occupied - cooldown

    # Check if pipeline is running
    pipeline = _get_pipeline(restaurant.restaurantid)
    is_running = pipeline.is_running if pipeline else False

    context = {
        'restaurant': restaurant,
        'cameras': cameras,
        'zones': list(zones.values(
            'zone_id', 'label', 'polygon_coords', 'capacity',
            'cooldown_seconds', 'status', 'person_count', 'color'
        )),
        'zones_json': json.dumps(list(zones.values(
            'zone_id', 'label', 'polygon_coords', 'capacity',
            'cooldown_seconds', 'status', 'person_count', 'color'
        ))),
        'total_tables': total,
        'occupied_tables': occupied,
        'cooldown_tables': cooldown,
        'available_tables': available,
        'occupancy_pct': round(occupied / total * 100, 1) if total > 0 else 0,
        'is_running': is_running,
    }

    return render(request, 'restaurant/occupancy_dashboard.html', context)


# ─── Zone Calibration ───────────────────────────────────────────────────────

@login_required(login_url='restaurantlogin')
def zone_calibrator(request):
    """Render the zone calibration page for drawing table ROIs."""
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
    except Restaurant.DoesNotExist:
        return redirect('restaurantlogin')

    cameras = CameraFeed.objects.filter(restaurant=restaurant)
    zones = TableZone.objects.filter(restaurant=restaurant)

    # Get static frame from the first camera (if exists)
    static_frame = None
    active_camera = cameras.first()
    if active_camera and active_camera.static_frame != "*":
        static_frame = active_camera.static_frame

    context = {
        'restaurant': restaurant,
        'cameras': cameras,
        'zones': list(zones.values(
            'zone_id', 'label', 'polygon_coords', 'capacity', 'cooldown_seconds', 'color'
        )),
        'zones_json': json.dumps(list(zones.values(
            'zone_id', 'label', 'polygon_coords', 'capacity', 'cooldown_seconds', 'color'
        ))),
        'static_frame': static_frame,
        'active_camera_id': active_camera.camera_id if active_camera else None,
    }

    return render(request, 'restaurant/zone_calibrator.html', context)


@csrf_exempt
@login_required(login_url='restaurantlogin')
def save_zones(request):
    """Save zone polygon definitions from the calibrator tool."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    try:
        restaurant = Restaurant.objects.get(owner=request.user)
        data = json.loads(request.body)
        zones_data = data.get('zones', [])
        camera_id = data.get('camera_id')

        camera = get_object_or_404(CameraFeed, camera_id=camera_id, restaurant=restaurant)

        # Delete existing zones for this camera and recreate
        TableZone.objects.filter(camera=camera, restaurant=restaurant).delete()

        created_zones = []
        for i, zone_data in enumerate(zones_data):
            zone = TableZone.objects.create(
                restaurant=restaurant,
                camera=camera,
                label=zone_data.get('label', f'Table {i + 1}'),
                polygon_coords=zone_data.get('polygon_coords', []),
                capacity=zone_data.get('capacity', 4),
                cooldown_seconds=zone_data.get('cooldown_seconds', 300),
                color=zone_data.get('color', '#00e676'),
            )
            created_zones.append({
                'zone_id': zone.zone_id,
                'label': zone.label,
            })

        return JsonResponse({
            'success': True,
            'message': f'{len(created_zones)} zones saved successfully',
            'zones': created_zones,
        })

    except Exception as e:
        logger.error(f"Save zones error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─── Camera / Video Upload ──────────────────────────────────────────────────

@csrf_exempt
@login_required(login_url='restaurantlogin')
def upload_camera_frame(request):
    """Upload a video file or static image for calibration / detection."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    try:
        restaurant = Restaurant.objects.get(owner=request.user)

        # Handle file upload
        uploaded_file = request.FILES.get('video_file') or request.FILES.get('image_file')
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)

        # Save uploaded file
        media_dir = os.path.join(settings.BASE_DIR, 'media', 'cv_uploads')
        os.makedirs(media_dir, exist_ok=True)

        file_ext = os.path.splitext(uploaded_file.name)[1]
        filename = f"restaurant_{restaurant.restaurantid}_{int(time.time())}{file_ext}"
        filepath = os.path.join(media_dir, filename)

        with open(filepath, 'wb+') as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        # Determine source type
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp'}
        source_type = 'video_file' if file_ext.lower() in video_exts else 'video_file'

        # Create or update camera feed
        camera, created = CameraFeed.objects.get_or_create(
            restaurant=restaurant,
            defaults={
                'name': 'Main Camera',
                'source_type': source_type,
                'source_path': filepath,
            }
        )
        if not created:
            camera.source_path = filepath
            camera.source_type = source_type

        # Extract first frame for calibration
        if file_ext.lower() in video_exts:
            from .cv_engine.utils import extract_first_frame
            static_frame = extract_first_frame(filepath)
            if static_frame:
                camera.static_frame = static_frame
        elif file_ext.lower() in image_exts:
            with open(filepath, 'rb') as f:
                camera.static_frame = base64.b64encode(f.read()).decode('utf-8')

        camera.save()

        return JsonResponse({
            'success': True,
            'camera_id': camera.camera_id,
            'static_frame': camera.static_frame if camera.static_frame != "*" else None,
            'message': 'File uploaded successfully',
        })

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─── Pipeline Control ────────────────────────────────────────────────────────

@csrf_exempt
@login_required(login_url='restaurantlogin')
def start_detection(request):
    """Start the CV detection pipeline for the restaurant."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    try:
        restaurant = Restaurant.objects.get(owner=request.user)

        # Check if already running
        existing = _get_pipeline(restaurant.restaurantid)
        if existing and existing.is_running:
            return JsonResponse({'success': True, 'message': 'Pipeline already running'})

        # Get camera and zones
        camera = CameraFeed.objects.filter(restaurant=restaurant).first()
        if not camera:
            return JsonResponse({'success': False, 'error': 'No camera configured. Upload a video first.'}, status=400)

        zones = TableZone.objects.filter(restaurant=restaurant, camera=camera)
        if not zones.exists():
            return JsonResponse({'success': False, 'error': 'No zones defined. Calibrate zones first.'}, status=400)

        # Prepare zone data
        zones_list = list(zones.values('zone_id', 'label', 'polygon_coords', 'cooldown_seconds'))

        # Initialize pipeline components
        from .cv_engine.detector import PersonDetector
        from .cv_engine.state_manager import StateManager
        from .cv_engine.pipeline import OccupancyPipeline

        detector = PersonDetector(model_path="yolov8n.pt", confidence=0.45)
        state_manager = StateManager()

        pipeline = OccupancyPipeline(
            detector=detector,
            state_manager=state_manager,
            table_zones=zones_list,
            source=camera.source_path,
            fps_target=5,
        )

        # Register callback to save snapshots to DB
        def on_status_update(statuses, summary):
            _save_occupancy_snapshot(restaurant, statuses)

        pipeline.on_update(on_status_update)

        # Store and start
        with _pipeline_lock:
            _active_pipelines[restaurant.restaurantid] = pipeline

        pipeline.start()

        return JsonResponse({
            'success': True,
            'message': 'Detection pipeline started',
        })

    except Exception as e:
        logger.error(f"Start detection error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@login_required(login_url='restaurantlogin')
def stop_detection(request):
    """Stop the CV detection pipeline."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    try:
        restaurant = Restaurant.objects.get(owner=request.user)

        pipeline = _get_pipeline(restaurant.restaurantid)
        if pipeline:
            pipeline.stop()
            with _pipeline_lock:
                del _active_pipelines[restaurant.restaurantid]

            # Reset all zones to available
            TableZone.objects.filter(restaurant=restaurant).update(
                status='available', person_count=0
            )

        return JsonResponse({'success': True, 'message': 'Detection stopped'})

    except Exception as e:
        logger.error(f"Stop detection error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─── Snapshot Saver (called from pipeline callback) ──────────────────────────

_last_snapshot_time = {}


def _save_occupancy_snapshot(restaurant, statuses):
    """Save occupancy snapshots to DB (throttled to every 30 seconds per zone)."""
    now = time.time()

    for zone_id, status_info in statuses.items():
        key = f"{restaurant.restaurantid}_{zone_id}"
        last_time = _last_snapshot_time.get(key, 0)

        if now - last_time < 30:  # Throttle: one snapshot per 30s per zone
            continue

        try:
            zone = TableZone.objects.get(zone_id=zone_id)
            zone.status = status_info.get("status", "available")
            zone.person_count = status_info.get("person_count", 0)
            zone.save()

            OccupancySnapshot.objects.create(
                zone=zone,
                status=status_info.get("status", "available"),
                person_count=status_info.get("person_count", 0),
                confidence=status_info.get("avg_confidence", 0.0),
            )
            _last_snapshot_time[key] = now

        except TableZone.DoesNotExist:
            logger.warning(f"Zone {zone_id} not found for snapshot")
        except Exception as e:
            logger.error(f"Snapshot save error: {e}")


# ─── REST API Endpoints ─────────────────────────────────────────────────────

@login_required(login_url='restaurantlogin')
def api_occupancy_status(request):
    """Return current occupancy status of all zones (JSON)."""
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
        zones = TableZone.objects.filter(restaurant=restaurant)

        pipeline = _get_pipeline(restaurant.restaurantid)
        is_running = pipeline.is_running if pipeline else False

        # Get live frame if pipeline is running
        live_frame = None
        if pipeline and pipeline.is_running:
            live_frame = pipeline.get_latest_frame_b64()

        zones_data = []
        for zone in zones:
            zones_data.append({
                'zone_id': zone.zone_id,
                'label': zone.label,
                'status': zone.status,
                'person_count': zone.person_count,
                'polygon_coords': zone.polygon_coords,
                'capacity': zone.capacity,
                'color': zone.color,
            })

        total = len(zones_data)
        occupied = sum(1 for z in zones_data if z['status'] == 'occupied')
        cooldown = sum(1 for z in zones_data if z['status'] == 'cooldown')

        return JsonResponse({
            'success': True,
            'is_running': is_running,
            'zones': zones_data,
            'summary': {
                'total': total,
                'occupied': occupied,
                'cooldown': cooldown,
                'available': total - occupied - cooldown,
                'occupancy_pct': round(occupied / total * 100, 1) if total > 0 else 0,
            },
            'live_frame': live_frame,
            'timestamp': timezone.now().isoformat(),
        })

    except Restaurant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Restaurant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='restaurantlogin')
def api_occupancy_analytics(request):
    """Return analytics data (hourly occupancy, turnover times, wait predictions)."""
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
        zones = TableZone.objects.filter(restaurant=restaurant)
        zones_list = list(zones.values('zone_id', 'label', 'polygon_coords'))

        # Get snapshots from the last 24 hours
        since = timezone.now() - timedelta(hours=24)
        snapshots = OccupancySnapshot.objects.filter(
            zone__restaurant=restaurant,
            timestamp__gte=since,
        ).select_related('zone')

        from .cv_engine.analytics import generate_analytics_report

        # Current statuses
        current_statuses = {}
        for zone in zones:
            current_statuses[zone.zone_id] = {
                'status': zone.status,
                'person_count': zone.person_count,
            }

        report = generate_analytics_report(
            snapshots=list(snapshots),
            table_zones=zones_list,
            current_statuses=current_statuses,
        )

        return JsonResponse({
            'success': True,
            **report,
            'timestamp': timezone.now().isoformat(),
        })

    except Restaurant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Restaurant not found'}, status=404)
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='restaurantlogin')
def api_occupancy_heatmap(request):
    """Return heatmap data for each zone."""
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
        zones = TableZone.objects.filter(restaurant=restaurant)
        zones_list = list(zones.values('zone_id', 'label', 'polygon_coords'))

        since = timezone.now() - timedelta(hours=24)
        snapshots = OccupancySnapshot.objects.filter(
            zone__restaurant=restaurant,
            timestamp__gte=since,
        )

        from .cv_engine.analytics import compute_heatmap_data
        heatmap = compute_heatmap_data(list(snapshots), zones_list)

        return JsonResponse({
            'success': True,
            'heatmap': heatmap,
            'timestamp': timezone.now().isoformat(),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
