from flask import Flask, request, jsonify
import socket
import datetime
import subprocess
import re
from threading import Lock
import win32print
import win32ui

app = Flask(__name__)

pinpad_ip = None
pinpad_port = 5000
pinpad_socket = None
lock = Lock()


def listar_impressoras():
    try:
        impressoras = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [printer[2] for printer in impressoras]
    except Exception as e:
        print(f"Erro ao listar impressoras: {e}")
        return []


def descobrir_ip_local():
    try:
        resultado = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5)
        match = re.search(r'IPv4[^\n]*:\s*([0-9.]+)', resultado.stdout)
        if match:
            return match.group(1)
    except Exception:
        pass
    return '127.0.0.1'


def conectar_pinpad(ip, port=5000):
    global pinpad_ip, pinpad_port, pinpad_socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        pinpad_ip = ip
        pinpad_port = port
        pinpad_socket = sock
        print(f"Conectado à PinPad {ip}:{port}")
        return True
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        return False


def enviar_comando(comando):
    global pinpad_socket
    if not pinpad_socket:
        return False
    try:
        pinpad_socket.sendall(comando.encode('utf-8'))
        return True
    except Exception as e:
        print(f"Erro ao enviar comando: {e}")
        return False


def receber_resposta(timeout=5):
    global pinpad_socket
    if not pinpad_socket:
        return None
    try:
        pinpad_socket.settimeout(timeout)
        dados = pinpad_socket.recv(1024)
        if not dados:
            return None
        return dados.decode('utf-8', errors='ignore').strip()
    except socket.timeout:
        return None
    except Exception as e:
        print(f"Erro ao receber resposta: {e}")
        return None


def imprimir_comprovante(impressora_nome, valor, estabelecimento='ESTABELECIMENTO', cnpj='00.000.000/0000-00'):
    try:
        hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        texto = (
            '=' * 40 + '\n'
            f'{estabelecimento.upper()}\n'
            '=' * 40 + '\n'
            'COMPROVANTE DE PAGAMENTO\n'
            '=' * 40 + '\n'
            f'CNPJ: {cnpj}\n'
            f'Data/Hora: {hora}\n'
            f'Valor: R$ {valor:.2f}\n'
            '=' * 40 + '\n'
            'STATUS: TRANSAÇÃO APROVADA\n'
            '=' * 40 + '\n'
            'Obrigado pela sua compra!\n'
            '=' * 40
        )

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(impressora_nome)
        hdc.StartDoc('Comprovante PinPad')
        hdc.StartPage()

        font = win32ui.CreateFont({
            'name': 'Courier New',
            'height': 18,
            'weight': 400,
        })
        hdc.SelectObject(font)

        y = 100
        for linha in texto.split('\n'):
            hdc.TextOut(100, y, linha)
            y += 25

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
        print(f'Comprovante impresso em {impressora_nome}')
        return True
    except Exception as e:
        print(f'Erro ao imprimir: {e}')
        return False


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'ip_local': descobrir_ip_local(),
        'pinpad_conectada': pinpad_socket is not None,
        'pinpad_ip': pinpad_ip
    })


@app.route('/api/conectar', methods=['POST'])
def conectar():
    global pinpad_ip, pinpad_port, pinpad_socket

    data = request.get_json(silent=True) or {}
    ip = data.get('ip')
    port = int(data.get('port', 5000))

    if not ip:
        return jsonify({'sucesso': False, 'erro': 'IP da PinPad não informado'})

    try:
        if pinpad_socket:
            pinpad_socket.close()
            pinpad_socket = None

        sucesso = conectar_pinpad(ip, port)
        return jsonify({'sucesso': sucesso, 'erro': None if sucesso else 'Falha na conexão'})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/processar', methods=['POST'])
def processar_transacao():
    global pinpad_ip, pinpad_port, pinpad_socket

    data = request.get_json(silent=True) or {}
    valor = float(data.get('valor', 0))

    if not pinpad_socket:
        return jsonify({'sucesso': False, 'erro': 'PinPad não conectada'})

    if valor <= 0:
        return jsonify({'sucesso': False, 'erro': 'Valor inválido'})

    try:
        with lock:
            if not enviar_comando(f'TRANSACAO|{valor:.2f}\n'):
                return jsonify({'sucesso': False, 'erro': 'Falha ao enviar valor'})

            resposta = receber_resposta(timeout=10)
            print(f'Resposta da PinPad: {resposta}')

            if resposta and 'APROVADA' in resposta.upper():
                impressora_nome = data.get('impressora', 'Microsoft Print to PDF')
                estabelecimento = data.get('estabelecimento', 'ESTABELECIMENTO')
                cnpj = data.get('cnpj', '00.000.000/0000-00')

                imprimir_comprovante(impressora_nome, valor, estabelecimento, cnpj)
                return jsonify({'sucesso': True, 'mensagem': 'Transação aprovada'})

            return jsonify({'sucesso': False, 'erro': 'Transação não aprovada pela PinPad'})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/impressoras', methods=['GET'])
def get_impressoras():
    return jsonify({'impressoras': listar_impressoras()})


@app.route('/api/cancelar', methods=['POST'])
def cancelar():
    if not pinpad_socket:
        return jsonify({'sucesso': False})
    try:
        enviar_comando('CANCELAR\n')
        return jsonify({'sucesso': True})
    except Exception:
        return jsonify({'sucesso': False})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
