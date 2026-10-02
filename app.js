// Variáveis globais
let pinpadConectada = false;
let serverIP = localStorage.getItem('serverIP') || window.location.hostname;
let serverPort = localStorage.getItem('serverPort') || 5001;

// Ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
    carregarConfiguracao();
    obterIPLocal();
});

// Obter IP local do navegador
function obterIPLocal() {
    // Tenta obter IP da rede local
    document.getElementById('ipServidor').value = window.location.hostname || 'localhost';
}

// Adicionar log
function adicionarLog(mensagem, tipo = 'info') {
    const logBox = document.getElementById('logBox');
    const entrada = document.createElement('div');
    entrada.className = `log-entry ${tipo}`;
    
    const hora = new Date().toLocaleTimeString('pt-BR');
    entrada.textContent = `[${hora}] ${mensagem}`;
    
    logBox.appendChild(entrada);
    logBox.scrollTop = logBox.scrollHeight;
}

// Conectar na PinPad
async function conectarPinpad() {
    const ipPinpad = document.getElementById('ipPinpad').value;
    const portaPinpad = document.getElementById('portaPinpad').value;
    
    if (!ipPinpad) {
        adicionarLog('❌ Digite o IP da PinPad', 'error');
        return;
    }
    
    const btnConectar = document.getElementById('btnConectar');
    btnConectar.disabled = true;
    btnConectar.textContent = 'Conectando...';
    
    adicionarLog('⏳ Testando conexão com PinPad...', 'warning');
    
    try {
        const response = await fetch(`http://${serverIP}:${serverPort}/api/conectar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                ip: ipPinpad,
                port: parseInt(portaPinpad)
            })
        });
        
        const resultado = await response.json();
        
        if (resultado.sucesso) {
            pinpadConectada = true;
            adicionarLog(`✅ PinPad conectada em ${ipPinpad}:${portaPinpad}`, 'success');
            document.getElementById('status').className = 'status conectado';
            document.getElementById('status').textContent = `✅ Status: Conectado (${ipPinpad})`;
            document.getElementById('pinpadInfo').textContent = `${ipPinpad}:${portaPinpad}`;
            document.getElementById('valor').disabled = false;
            document.getElementById('btnProcessar').disabled = false;
            document.getElementById('btnCancelar').disabled = false;
            btnConectar.textContent = '✓ Conectado';
            btnConectar.style.background = '#28a745';
        } else {
            adicionarLog(`❌ Erro: ${resultado.erro}`, 'error');
            document.getElementById('status').className = 'status desconectado';
            document.getElementById('status').textContent = '❌ Status: Desconectado';
        }
    } catch (erro) {
        adicionarLog(`❌ Erro de conexão com servidor: ${erro.message}`, 'error');
        document.getElementById('status').className = 'status desconectado';
        document.getElementById('status').textContent = '❌ Status: Erro';
    } finally {
        btnConectar.disabled = false;
    }
}

// Processar transação
async function processarTransacao() {
    const valor = parseFloat(document.getElementById('valor').value);
    
    if (!valor || valor <= 0) {
        adicionarLog('❌ Digite um valor válido', 'error');
        return;
    }
    
    if (!pinpadConectada) {
        adicionarLog('❌ PinPad não conectada', 'error');
        return;
    }
    
    document.getElementById('modalProcessando').classList.add('ativo');
    adicionarLog(`💰 Processando transação de R$ ${valor.toFixed(2)}...`, 'info');
    
    try {
        const response = await fetch(`http://${serverIP}:${serverPort}/api/processar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                valor: valor
            })
        });
        
        const resultado = await response.json();
        
        if (resultado.sucesso) {
            adicionarLog('✅ Transação aprovada!', 'success');
            
            document.getElementById('modalValor').textContent = `R$ ${valor.toFixed(2)}`;
            document.getElementById('modalProcessando').classList.remove('ativo');
            document.getElementById('modalAprovado').classList.add('ativo');
            
            // Limpar valor
            document.getElementById('valor').value = '';
            
        } else {
            adicionarLog(`❌ Erro: ${resultado.erro}`, 'error');
            document.getElementById('modalProcessando').classList.remove('ativo');
            document.getElementById('modalMensagemErro').textContent = resultado.erro;
            document.getElementById('modalErro').classList.add('ativo');
        }
    } catch (erro) {
        adicionarLog(`❌ Erro: ${erro.message}`, 'error');
        document.getElementById('modalProcessando').classList.remove('ativo');
        document.getElementById('modalMensagemErro').textContent = erro.message;
        document.getElementById('modalErro').classList.add('ativo');
    }
}

// Cancelar transação
async function cancelarTransacao() {
    if (confirm('Deseja cancelar a transação?')) {
        document.getElementById('valor').value = '';
        adicionarLog('Transação cancelada', 'warning');
        
        try {
            await fetch(`http://${serverIP}:${serverPort}/api/cancelar`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
        } catch (erro) {
            // Ignorar erro
        }
    }
}

// Fechar modal
function fecharModal() {
    document.getElementById('modalProcessando').classList.remove('ativo');
    document.getElementById('modalAprovado').classList.remove('ativo');
    document.getElementById('modalErro').classList.remove('ativo');
}

// Abrir configurações
function abrirConfiguracao() {
    document.getElementById('settingsModal').classList.add('ativo');
    carregarImpressoras();
}

// Fechar configurações
function fecharConfiguracao() {
    document.getElementById('settingsModal').classList.remove('ativo');
}

// Carregar configuração salva
function carregarConfiguracao() {
    document.getElementById('cnpj').value = localStorage.getItem('cnpj') || '';
    document.getElementById('estabelecimento').value = localStorage.getItem('estabelecimento') || '';
    document.getElementById('ipPinpad').value = localStorage.getItem('ipPinpad') || '192.168.1.100';
    document.getElementById('portaPinpad').value = localStorage.getItem('portaPinpad') || '5000';
    document.getElementById('ipServidor').value = localStorage.getItem('ipServidor') || window.location.hostname;
    document.getElementById('portaServidor').value = localStorage.getItem('portaServidor') || '5001';
}

// Salvar configuração
function salvarConfiguracao() {
    localStorage.setItem('cnpj', document.getElementById('cnpj').value);
    localStorage.setItem('estabelecimento', document.getElementById('estabelecimento').value);
    localStorage.setItem('ipPinpad', document.getElementById('ipPinpad').value);
    localStorage.setItem('portaPinpad', document.getElementById('portaPinpad').value);
    localStorage.setItem('ipServidor', document.getElementById('ipServidor').value);
    localStorage.setItem('portaServidor', document.getElementById('portaServidor').value);
    
    adicionarLog('✅ Configurações salvas!', 'success');
    fecharConfiguracao();
    location.reload();
}

// Carregar impressoras
async function carregarImpressoras() {
    try {
        const response = await fetch(`http://${serverIP}:${serverPort}/api/impressoras`);
        const resultado = await response.json();
        
        const select = document.getElementById('impressora');
        select.innerHTML = '<option value="">Selecionar impressora...</option>';
        
        if (resultado.impressoras && resultado.impressoras.length > 0) {
            resultado.impressoras.forEach(imp => {
                const option = document.createElement('option');
                option.value = imp;
                option.textContent = imp;
                select.appendChild(option);
            });
        }
    } catch (erro) {
        console.error('Erro ao carregar impressoras:', erro);
    }
}

// Fechar modals ao clicar fora
document.addEventListener('click', function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target == modal) {
        fecharConfiguracao();
    }
});
