from flask import Flask, request, jsonify, send_from_directory
import socket
import datetime
import json
from pathlib import Path
from threading import Lock

app = Flask(__name__, static_folder='.', static_url_path='')

pinpad_ip = None
pinpad_port = 5000
pinpad_socket = None
lock = Lock()

CONFIG_FILE = Path('config.json')


def carregar_config():
    """Carrega configurações do arquivo"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    config_padrao = {
        'cnpj': '00.000.000/0000-00',
        'estabelecimento': 'ESTABELECIMENTO',
        'ip_pinpad': '192.168.1.100',
        'porta_pinpad': 5000,
        'ip_pc': '192.168.1.50',
        'porta_servidor': 5001
    }
    
    salvar_config(config_padrao)
    return config_padrao


def salvar_config(config):
    """Salva configurações no arquivo"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")


def conectar_pinpad(ip, port=5000):
    """Conecta na PinPad via IP fixo"""
    global pinpad_ip, pinpad_port, pinpad_socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        pinpad_ip = ip
        pinpad_port = port
        pinpad_socket = sock
        print(f"✓ Conectado à PinPad {ip}:{port}")
        return True
    except Exception as e:
        print(f"✗ Erro ao conectar: {e}")
        return False


def enviar_comando(comando):
    """Envia comando para a PinPad"""
    global pinpad_socket
    if not pinpad_socket:
        return False
    try:
        pinpad_socket.sendall(comando.encode('utf-8'))
        print(f"→ Enviado para PinPad: {comando.strip()}")
        return True
    except Exception as e:
        print(f"✗ Erro ao enviar: {e}")
        return False


def receber_resposta(timeout=10):
    """Recebe resposta da PinPad"""
    global pinpad_socket
    if not pinpad_socket:
        return None
    try:
        pinpad_socket.settimeout(timeout)
        dados = pinpad_socket.recv(1024)
        if not dados:
            return None
        resposta = dados.decode('utf-8', errors='ignore').strip()
        print(f"← Recebido da PinPad: {resposta}")
        return resposta
    except socket.timeout:
        print("✗ Timeout aguardando resposta da PinPad")
        return None
    except Exception as e:
        print(f"✗ Erro ao receber: {e}")
        return None


def gerar_comprovante(valor, cnpj, estabelecimento):
    """Gera texto do comprovante"""
    hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    comprovante = (
        '======================================\n'
        f'{estabelecimento.upper():^38}\n'
        '======================================\n'
        'COMPROVANTE DE PAGAMENTO\n'
        '======================================\n'
        f'CNPJ: {cnpj}\n'
        f'Data/Hora: {hora}\n'
        f'Valor: R$ {valor:>30.2f}\n'
        '======================================\n'
        'STATUS: TRANSACAO APROVADA\n'
        '======================================\n'
        'Obrigado pela sua compra!\n'
        '======================================\n'
    )
    return comprovante


@app.route('/')
def serve_index():
    """Serve a página HTML"""
    return send_from_directory('.', 'index.html')


@app.route('/app.js')
def serve_app():
    """Serve o arquivo JavaScript"""
    return send_from_directory('.', 'app.js')


@app.route('/api/health', methods=['GET'])
def health():
    """Verifica status do servidor"""
    config = carregar_config()
    return jsonify({
        'status': 'ok',
        'servidor': f"{config.get('ip_pc', '192.168.1.50')}:{config.get('porta_servidor', 5001)}",
        'pinpad_conectada': pinpad_socket is not None,
        'pinpad_ip': pinpad_ip,
        'pinpad_port': pinpad_port,
        'timestamp': datetime.datetime.now().isoformat()
    })


@app.route('/api/conectar', methods=['POST'])
def conectar():
    """Conecta na PinPad usando IP fixo"""
    global pinpad_socket

    data = request.get_json(silent=True) or {}
    ip = data.get('ip')
    port = int(data.get('port', 5000))

    if not ip:
        return jsonify({'sucesso': False, 'erro': 'IP da PinPad não informado'})

    try:
        # Fecha conexão anterior se existir
        if pinpad_socket:
            try:
                pinpad_socket.close()
            except:
                pass
            pinpad_socket = None

        # Conecta na PinPad
        sucesso = conectar_pinpad(ip, port)
        
        if sucesso:
            # Testa com PING
            enviar_comando('PING\n')
            resposta = receber_resposta(timeout=3)
        
        # Salva IP da PinPad na config
        if sucesso:
            config = carregar_config()
            config['ip_pinpad'] = ip
            config['porta_pinpad'] = port
            salvar_config(config)

        return jsonify({
            'sucesso': sucesso,
            'erro': None if sucesso else 'Falha ao conectar na PinPad',
            'ip': ip,
            'port': port,
            'mensagem': f'Conectado em {ip}:{port}' if sucesso else 'Erro de conexão'
        })
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/processar', methods=['POST'])
def processar_transacao():
    """Processa transação na PinPad"""
    global pinpad_socket

    data = request.get_json(silent=True) or {}
    valor = float(data.get('valor', 0))

    if not pinpad_socket:
        return jsonify({'sucesso': False, 'erro': 'PinPad não conectada'})

    if valor <= 0:
        return jsonify({'sucesso': False, 'erro': 'Valor inválido'})

    try:
        with lock:
            config = carregar_config()
            cnpj = config.get('cnpj', '00.000.000/0000-00')
            estabelecimento = config.get('estabelecimento', 'ESTABELECIMENTO')
            
            print(f"\n{'='*50}")
            print(f"💳 NOVA TRANSAÇÃO")
            print(f"Valor: R$ {valor:.2f}")
            print(f"Estabelecimento: {estabelecimento}")
            print(f"PinPad IP: {pinpad_ip}")
            print(f"{'='*50}\n")

            # Envia valor para PinPad
            comando = f"TRANSACAO|{valor:.2f}|{estabelecimento}|{cnpj}\n"
            if not enviar_comando(comando):
                return jsonify({'sucesso': False, 'erro': 'Falha ao enviar para PinPad'})

            print("⏳ Aguardando processamento na PinPad...")
            print("🖥️  Visor da PinPad deve mostrar: 'TRANSACAO APROVADA'\n")

            # Aguarda resposta da PinPad
            resposta = receber_resposta(timeout=30)
            
            if not resposta:
                return jsonify({'sucesso': False, 'erro': 'Timeout - PinPad não respondeu'})

            # Verifica aprovação
            if 'APROVADA' in resposta.upper() or 'APROVADO' in resposta.upper():
                print("✓ TRANSAÇÃO APROVADA!")
                print("✓ Visor da PinPad exibindo: 'TRANSACAO APROVADA'")
                print("✓ Impressorinha iniciando impressão do comprovante...\n")

                # Gera comprovante
                comprovante = gerar_comprovante(valor, cnpj, estabelecimento)
                
                # Envia para PinPad imprimir
                comando_print = f"PRINT\n{comprovante}\nFIM_PRINT\n"
                enviar_comando(comando_print)

                # Salva na log
                salvar_transacao(valor, cnpj, estabelecimento, 'APROVADA')

                return jsonify({
                    'sucesso': True,
                    'mensagem': 'Transação aprovada!',
                    'valor': valor,
                    'estabelecimento': estabelecimento,
                    'cnpj': cnpj,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'comprovante': comprovante
                })
            else:
                print(f"✗ TRANSAÇÃO RECUSADA!")
                print(f"Resposta da PinPad: {resposta}\n")
                salvar_transacao(valor, cnpj, estabelecimento, 'RECUSADA')
                
                return jsonify({
                    'sucesso': False,
                    'erro': 'Transação recusada pela PinPad',
                    'resposta': resposta
                })

    except Exception as e:
        print(f"✗ ERRO: {e}\n")
        return jsonify({'sucesso': False, 'erro': str(e)})


def salvar_transacao(valor, cnpj, estabelecimento, status):
    """Salva histórico de transações"""
    try:
        arquivo = Path('transacoes.log')
        hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        linha = f"{hora} | R$ {valor:.2f} | {estabelecimento} | {cnpj} | {status}\n"
        
        with open(arquivo, 'a', encoding='utf-8') as f:
            f.write(linha)
        print(f"✓ Transação salva em log")
    except Exception as e:
        print(f"Erro ao salvar log: {e}")


@app.route('/api/cancelar', methods=['POST'])
def cancelar():
    """Cancela transação"""
    if not pinpad_socket:
        return jsonify({'sucesso': False, 'erro': 'PinPad não conectada'})
    try:
        enviar_comando('CANCELAR\n')
        resposta = receber_resposta(timeout=5)
        print("✗ Transação cancelada\n")
        return jsonify({'sucesso': True, 'resposta': resposta})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Retorna configurações"""
    config = carregar_config()
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def save_config():
    """Salva configurações"""
    data = request.get_json(silent=True) or {}
    config = carregar_config()
    
    if 'cnpj' in data:
        config['cnpj'] = data['cnpj']
    if 'estabelecimento' in data:
        config['estabelecimento'] = data['estabelecimento']
    if 'ip_pinpad' in data:
        config['ip_pinpad'] = data['ip_pinpad']
    if 'porta_pinpad' in data:
        config['porta_pinpad'] = data['porta_pinpad']
    
    salvar_config(config)
    print(f"✓ Configurações salvas")
    
    return jsonify({'sucesso': True, 'config': config})


@app.route('/api/transacoes', methods=['GET'])
def get_transacoes():
    """Retorna histórico de transações"""
    try:
        arquivo = Path('transacoes.log')
        if not arquivo.exists():
            return jsonify({'transacoes': [], 'total': 0})
        
        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
        
        return jsonify({
            'transacoes': linhas[-50:],
            'total': len(linhas)
        })
    except Exception as e:
        return jsonify({'transacoes': [], 'total': 0, 'erro': str(e)})


if __name__ == '__main__':
    config = carregar_config()
    ip_pc = config.get('ip_pc', '192.168.1.50')
    porta = config.get('porta_servidor', 5001)
    
    print("\n" + "="*60)
    print("🚀 SERVIDOR PINPAD - IP FIXO LOCAL")
    print("="*60)
    print(f"\n📱 Acesse no celular: http://{ip_pc}:{porta}")
    print(f"🖥️  Servidor rodando em: http://0.0.0.0:{porta}")
    print(f"\n⚙️  Configurações carregadas:")
    print(f"   - CNPJ: {config.get('cnpj')}")
    print(f"   - Estabelecimento: {config.get('estabelecimento')}")
    print(f"   - IP da PinPad: {config.get('ip_pinpad')}")
    print(f"   - Porta PinPad: {config.get('porta_pinpad')}")
    print(f"\n✅ Servidor pronto para uso!")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)
