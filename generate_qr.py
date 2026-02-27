import qrcode
import socket
import os

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def generate():
    ip = get_local_ip()
    url = f"http://{ip}:5173"
    
    print(f"--- Generating Access QR Code ---")
    print(f"Your Local URL: {url}")
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to public folder so the React app can show it if needed
    output_path = "public/access_qr.png"
    img.save(output_path)
    
    print(f"Success! QR Code saved to: {output_path}")
    print(f"Anyone on your Wi-Fi can scan this to open the Medical Assist OS.")

if __name__ == "__main__":
    generate()
