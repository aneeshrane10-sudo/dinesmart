import random
import math

def generate_superincreasing_sequence(n):
    """Generate a superincreasing sequence for the private key"""
    sequence = []
    total = 0
    for _ in range(n):
        next_element = random.randint(total + 1, 2 * (total + 1))
        sequence.append(next_element)
        total += next_element
    return sequence

def create_public_key(private_key, q, r):
    """Create public key from private key using q and r"""
    return [(r * element) % q for element in private_key]

def extended_gcd(a, b):
    """Extended Euclidean algorithm to find modular inverse"""
    if a == 0:
        return (b, 0, 1)
    else:
        g, y, x = extended_gcd(b % a, a)
        return (g, x - (b // a) * y, y)

def mod_inverse(a, m):
    """Find modular inverse of a under modulo m"""
    g, x, y = extended_gcd(a, m)
    if g != 1:
        return None  # modular inverse doesn't exist
    else:
        return x % m

def encrypt(message, public_key):
    """Encrypt message using public key"""
    binary_message = ''.join(format(ord(c), '08b') for c in message)
    # Pad with zeros if necessary to match key length
    if len(binary_message) % len(public_key) != 0:
        binary_message += '0' * (len(public_key) - (len(binary_message) % len(public_key)))
    
    ciphertext = []
    for i in range(0, len(binary_message), len(public_key)):
        chunk = binary_message[i:i+len(public_key)]
        total = sum(public_key[j] for j in range(len(chunk)) if chunk[j] == '1')
        ciphertext.append(total)
    return ciphertext

def decrypt(ciphertext, private_key, q, r):
    """Decrypt ciphertext using private key, q, and r"""
    r_inv = mod_inverse(r, q)
    decrypted_numbers = [(num * r_inv) % q for num in ciphertext]
    
    message_bits = []
    for num in decrypted_numbers:
        # Solve the superincreasing subset sum problem
        bits = []
        remaining = num
        for element in reversed(private_key):
            if remaining >= element:
                bits.append('1')
                remaining -= element
            else:
                bits.append('0')
        # Reverse to get correct order
        message_bits.extend(reversed(bits))
    
    # Convert bits to string
    message = ''
    for i in range(0, len(message_bits), 8):
        byte = message_bits[i:i+8]
        if len(byte) < 8:
            break  # discard incomplete byte
        message += chr(int(''.join(byte), 2))
    return message

# Example usage
if __name__ == "__main__":
    # Parameters
    n = 8  # size of the knapsack (private key length)
    
    # Generate private key (superincreasing sequence)
    private_key = generate_superincreasing_sequence(n)
    print(f"Private key (superincreasing sequence): {private_key}")
    
    # Choose q greater than sum of all elements in private key
    q = sum(private_key) + random.randint(1, 100)
    
    # Choose r coprime with q
    while True:
        r = random.randint(2, q-1)
        if math.gcd(r, q) == 1:
            break
    
    print(f"q: {q}, r: {r}")
    
    # Generate public key
    public_key = create_public_key(private_key, q, r)
    print(f"Public key: {public_key}")
    
    # Message to encrypt
    message = "Hi!"
    print(f"\nOriginal message: {message}")
    
    # Encryption
    ciphertext = encrypt(message, public_key)
    print(f"Ciphertext: {ciphertext}")
    
    # Decryption
    decrypted_message = decrypt(ciphertext, private_key, q, r)
    print(f"Decrypted message: {decrypted_message}")