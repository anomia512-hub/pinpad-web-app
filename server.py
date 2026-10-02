from flask import Flask, request, jsonify, send_from_directory
import socket
import datetime
import json
from pathlib import Path
from threading import Lock
import time

app = Flask(__name__, static_folder='.', static_url_path='')

# Variáveis globais
smartpos_socket = None
lock = Lock()
CONFIG_FILE = Path('config.json')

# Tipos de SmartPOS suportados
TIPOS_SMARTPOS = {
    'cielo': {
        'nome': 'Cielo SmartPOS',
        'porta_padrao': 9000,
        'protocolo': 'cielo'
    },
    'stone': {
        'nome': 'Stone SmartPOS',
        'porta_padrao': 12345,
        'protocolo': 'stone'
    }
}


def carregar_config():
    """Carrega configurações do arquivo JSON"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    config_padrao = {
        'cnpj': '00.000.000/0000-00',
        'estabelecimento': 'ESTABELECIMENTO',
        'tipo_smartpos': 'cielo',
        'ip_smartpos': '192.168.0.100',
        'porta_smartpos': 9000,
        'timeout': 15,
        'ip_pc': '192.168.1.50',
        'porta_servidor': 5001
    }
    salvar_config(config_padrao)
    return config_padrao


def salvar_config(config):
    """Salva configurações no arquivo JSON"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Erro ao salvar config: {e}')


def conectar_smartpos(ip, port, tipo='cielo'):
    """Conecta na SmartPOS via IP fixo ou dinâmico"""
    global smartpos_socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((ip, port))
        smartpos_socket = sock
        print(f'✓ Conectado em {TIPOS_SMARTPOS[tipo]["nome"]} ({ip}:{port})')
        return True
    except Exception as e:
        print(f'✗ Erro ao conectar: {e}')
        return False


def enviar_comando_cielo(comando):
    """Envia comando para Cielo SmartPOS"""
    global smartpos_socket
    if not smartpos_socket:
        return False
    try:
        smartpos_socket.sendall(comando.encode('utf-8'))
        print(f'→ Cielo: {comando.strip()}')
        return True
    except Exception as e:
        print(f'✗ Erro ao enviar: {e}')
        return False


def enviar_comando_stone(comando):
    """Envia comando para Stone SmartPOS"""
    global smartpos_socket
    if not smartpos_socket:
        return False
    try:
        smartpos_socket.sendall(comando.encode('utf-8'))
        print(f'→ Stone: {comando.strip()}')
        return True
    except Exception as e:
        print(f'✗ Erro ao enviar: {e}')
        return False


def receber_resposta(timeout=15):
    """Recebe resposta da SmartPOS"""
    global smartpos_socket
    if not smartpos_socket:
        return None
    try:
        smartpos_socket.settimeout(timeout)
        dados = smartpos_socket.recv(2048)
        if not dados:
            return None
        resposta = dados.decode('utf-8', errors='ignore').strip()
        print(f'← Recebido: {resposta}')
        return resposta
    except socket.timeout:
        print('✗ Timeout aguardando resposta')
        return None
    except Exception as e:
        print(f'✗ Erro ao receber: {e}')
        return None


def processar_cielo(valor, cnpj, estabelecimento):
    """Processa transação na Cielo SmartPOS"""
    global smartpos_socket

    try:
        # Cielo usa protocolo específico
        # Formato: VALOR|valor|CNPJ|estabelecimento
        
        comando_valor = f"VALOR|{valor:.2f}|{cnpj}|{estabelecimento}\n"
        
        if not enviar_comando_cielo(comando_valor):
            return False, "Falha ao enviar valor"
        
        time.sleep(1)
        
        # Envia comando para processar
        if not enviar_comando_cielo("PROCESSAR\n"):
            return False, "Falha ao enviar comando PROCESSAR"
        
        # Aguarda resposta de aprovação
        resposta = receber_resposta(timeout=20)
        
        if not resposta:
            return False, "Timeout aguardando resposta"
        
        if 'APROVADA' in resposta.upper() or 'APROVADO' in resposta.upper() or 'OK' in resposta.upper():
            # Envia mensagem para visor
            visor_msg = "TRANSACAO APROVADA\n"
            enviar_comando_cielo(visor_msg)
            time.sleep(1)
            
            # Envia comando de impressão
            comprovante = gerar_comprovante(valor, cnpj, estabelecimento)
            print_cmd = f"IMPRIMIR\n{comprovante}\nFIM_IMPRIMIR\n"
            enviar_comando_cielo(print_cmd)
            
            return True, "Transação aprovada - Comprovante impresso"
        else:
            return False, f"Transação recusada: {resposta}"
    
    except Exception as e:
        return False, f"Erro ao processar: {e}"


def processar_stone(valor, cnpj, estabelecimento):
    """Processa transação na Stone SmartPOS"""
    global smartpos_socket

    try:
        # Stone usa protocolo diferente
        # Formato: OK\nVALOR:valor\nCNPJ:cnpj\nESTABELECIMENTO:estabelecimento
        
        # Envia OK inicial
        if not enviar_comando_stone("OK\n"):
            return False, "Falha na confirmação inicial"
        
        resposta_ok = receber_resposta(timeout=5)
        
        # Envia dados da transação
        dados_transacao = (
            f"VALOR:{valor:.2f}\n"
            f"CNPJ:{cnpj}\n"
            f"ESTABELECIMENTO:{estabelecimento}\n"
        )
        
        if not enviar_comando_stone(dados_transacao):
            return False, "Falha ao enviar dados da transação"
        
        # Aguarda processamento
        resposta = receber_resposta(timeout=20)
        
        if not resposta:
            return False, "Timeout aguardando resposta"
        
        if 'APROVADA' in resposta.upper() or 'APROVADO' in resposta.upper():
            # Envia mensagem para visor
            visor_msg = "TRANSACAO APROVADA\n"
            enviar_comando_stone(visor_msg)
            time.sleep(1)
            
            # Envia comando de impressão
            comprovante = gerar_comprovante(valor, cnpj, estabelecimento)
            print_cmd = f"PRINT\n{comprovante}\nEND_PRINT\n"
            enviar_comando_stone(print_cmd)
            
            return True, "Transação aprovada - Comprovante impresso"
        else:
            return False, f"Transação recusada: {resposta}"
    
    except Exception as e:
        return False, f"Erro ao processar: {e}"


def gerar_comprovante(valor, cnpj, estabelecimento):
    """Gera texto do comprovante formatado"""
    hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    return (
        '=======================================\n'
        f'{estabelecimento.upper():^39}\n'
        '=======================================\n'
        'COMPROVANTE DE PAGAMENTO\n'
        '=======================================\n'
        f'CNPJ: {cnpj}\n'
        f'Data/Hora: {hora}\n'
        f'Valor: R$ {valor:.2f}\n'
        '=======================================\n'
        'STATUS: TRANSACAO APROVADA\n'
        '=======================================\n'
        'Obrigado pela sua compra!\n'
        '=======================================\n'
    )


def salvar_transacao(valor, cnpj, estabelecimento, tipo, status):
    """Salva histórico de transações"""
    try:
        arquivo = Path('transacoes.log')
        hora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        linha = f'{hora} | {tipo} | R$ {valor:.2f} | {estabelecimento} | {cnpj} | {status}\n'
        with open(arquivo, 'a', encoding='utf-8') as f:
            f.write(linha)
    except Exception as e:
        print(f'Erro ao salvar: {e}')


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/app.js')
def app_js():
    return send_from_directory('.', 'app.js')


@app.route('/api/health', methods=['GET'])
def health():
    config = carregar_config()
    return jsonify({
        'status': 'ok',
        'smartpos_conectada': smartpos_socket is not None,
        'tipo_smartpos': config.get('tipo_smartpos'),
        'ip_pc': config.get('ip_pc'),
        'porta_servidor': config.get('porta_servidor')
    })


@app.route('/api/tipos', methods=['GET'])
def tipos_smartpos():
    """Retorna tipos de SmartPOS disponíveis"""
    tipos = []
    for chave, info in TIPOS_SMARTPOS.items():
        tipos.append({
            'id': chave,
            'nome': info['nome'],
            'porta_padrao': info['porta_padrao']
        })
    return jsonify({'tipos': tipos})


@app.route('/api/conectar', methods=['POST'])
def conectar():
    """Conecta na SmartPOS"""
    global smartpos_socket
    
    data = request.get_json(silent=True) or {}
    ip = data.get('ip')
    porta = int(data.get('porta', 9000))
    tipo = data.get('tipo', 'cielo')

    if not ip:
        return jsonify({'sucesso': False, 'erro': 'IP da SmartPOS não informado'})

    if tipo not in TIPOS_SMARTPOS:
        return jsonify({'sucesso': False, 'erro': f'Tipo de SmartPOS inválido: {tipo}'})

    try:
        # Fecha conexão anterior
        if smartpos_socket:
            try:
                smartpos_socket.close()
            except Exception:
                pass
            smartpos_socket = None

        # Conecta na SmartPOS
        sucesso = conectar_smartpos(ip, porta, tipo)

        if sucesso:
            config = carregar_config()
            config['tipo_smartpos'] = tipo
            config['ip_smartpos'] = ip
            config['porta_smartpos'] = porta
            salvar_config(config)

        return jsonify({
            'sucesso': sucesso,
            'erro': None if sucesso else 'Falha ao conectar',
            'tipo': TIPOS_SMARTPOS[tipo]['nome'],
            'ip': ip,
            'porta': porta
        })
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/processar', methods=['POST'])
def processar():
    """Processa transação na SmartPOS (Cielo ou Stone)"""
    global smartpos_socket

    data = request.get_json(silent=True) or {}
    valor = float(data.get('valor', 0))

    if not smartpos_socket:
        return jsonify({'sucesso': False, 'erro': 'SmartPOS não conectada'})

    if valor <= 0:
        return jsonify({'sucesso': False, 'erro': 'Valor inválido'})

    try:
        with lock:
            config = carregar_config()
            cnpj = config.get('cnpj', '00.000.000/0000-00')
            estabelecimento = config.get('estabelecimento', 'ESTABELECIMENTO')
            tipo = config.get('tipo_smartpos', 'cielo')

            print(f"\n{'='*50}")
            print(f"💳 NOVA TRANSAÇÃO - {TIPOS_SMARTPOS[tipo]['nome']}")
            print(f"Valor: R$ {valor:.2f}")
            print(f"Estabelecimento: {estabelecimento}")
            print(f"{'='*50}\n")

            # Processa conforme tipo de SmartPOS
            if tipo == 'cielo':
                sucesso, mensagem = processar_cielo(valor, cnpj, estabelecimento)
            elif tipo == 'stone':
                sucesso, mensagem = processar_stone(valor, cnpj, estabelecimento)
            else:
                return jsonify({'sucesso': False, 'erro': 'Tipo de SmartPOS não reconhecido'})

            if sucesso:
                salvar_transacao(valor, cnpj, estabelecimento, tipo.upper(), 'APROVADA')
                return jsonify({
                    'sucesso': True,
                    'mensagem': mensagem,
                    'valor': valor,
                    'tipo': tipo
                })
            else:
                salvar_transacao(valor, cnpj, estabelecimento, tipo.upper(), 'RECUSADA')
                return jsonify({
                    'sucesso': False,
                    'erro': mensagem,
                    'tipo': tipo
                })

    except Exception as e:
        print(f"✗ ERRO: {e}\n")
        return jsonify({'sucesso': False, 'erro': str(e)})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Retorna configurações"""
    return jsonify(carregar_config())


@app.route('/api/config', methods=['POST'])
def save_config_api():
    """Salva configurações"""
    data = request.get_json(silent=True) or {}
    config = carregar_config()
    
    if 'cnpj' in data:
        config['cnpj'] = data['cnpj']
    if 'estabelecimento' in data:
        config['estabelecimento'] = data['estabelecimento']
    if 'tipo_smartpos' in data:
        config['tipo_smartpos'] = data['tipo_smartpos']
    if 'ip_smartpos' in data:
        config['ip_smartpos'] = data['ip_smartpos']
    if 'porta_smartpos' in data:
        config['porta_smartpos'] = data['porta_smartpos']
    
    salvar_config(config)
    return jsonify({'sucesso': True, 'config': config})


@app.route('/api/transacoes', methods=['GET'])
def transacoes():
    """Retorna histórico de transações"""
    try:
        arquivo = Path('transacoes.log')
        if not arquivo.exists():
            return jsonify({'transacoes': []})
        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()
        return jsonify({'transacoes': linhas[-50:]})
    except Exception as e:
        return jsonify({'transacoes': [], 'erro': str(e)})


if __name__ == '__main__':
    config = carregar_config()
    ip_pc = config.get('ip_pc', '192.168.1.50')
    porta = config.get('porta_servidor', 5001)
    
    print('\n' + '='*60)
    print('SERVIDOR SMARTPOS - CIELO & STONE')
    print('='*60)
    print(f'Celular acessa: http://{ip_pc}:{porta}')
    print(f'SmartPOS tipo: {config.get("tipo_smartpos", "cielo")}')
    print(f'SmartPOS IP: {config.get("ip_smartpos", "192.168.0.100")}')
    print('='*60 + '\n')
    
    app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)
