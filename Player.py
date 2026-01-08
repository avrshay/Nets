import socket


def run_client():
    # הכתובת והפורט חייבים להיות זהים לאלו שבשרת
    HOST = ???
    PORT = 13122

    # יצירת סוקט
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        # התחברות לשרת
        client_socket.connect((HOST, PORT))

        # שליחת הודעה
        message = "Hello, Server! This is the client."
        print(f"Sending: {message}")
        client_socket.sendall(message.encode('utf-8'))

        # קבלת תשובה מהשרת
        data = client_socket.recv(1024)

    print(f"Received from server: {data.decode('utf-8')}")


if __name__ == '__main__':
    run_client()