# VigiaAI — Central integrada

Monitoramento local de pessoas, possíveis quedas e EPIs selecionados, com câmera,
vídeos gravados, coleta de amostras e notificações por e-mail.

A atualização de 31/10/2026 reúne a Central 2.1 e as correções locais de reanálise
de EPI, óculos e baixa cadência. Os três modelos foram preservados; não houve novo
treinamento nem comprovação de ganho de precisão industrial.

## Executar no computador já preparado

Na pasta principal do projeto:

```powershell
.\iniciar_vigiaai.ps1 -CPU -Porta 5001
```

Alternativa sem executar o arquivo PowerShell:

```powershell
$env:VIGIAAI_DEVICE = 'cpu'
$env:VIGIAAI_PORTA = '5001'
.\.venv\Scripts\python.exe main.py
```

Abra **http://127.0.0.1:5001**. Na Central, selecione **Câmera ao vivo**, clique em
**Buscar câmeras**, escolha o dispositivo e inicie. O painel clássico e a coleta
continuam em **http://127.0.0.1:5001/legado**. Também é possível enviar uma gravação
local, pausar, buscar trechos e reiniciar a análise.

Encerre com `Ctrl+C`. Se outra versão já estiver usando a porta ou a câmera, encerre-a
antes de iniciar esta. O servidor aceita somente acesso local, sem autenticação.
As duas telas compartilham uma análise por processo.

O iniciador procura `VIGIAAI_PYTHON`, depois o arquivo privado `.runtime-python`,
depois a `.venv` da própria pasta. Na atualização deste computador, a `.venv`
existente foi mantida, sem reinstalar pacotes. Preserve também seu `.env` e
`config_epi.json`; não substitua suas credenciais por valores do exemplo.

## Instalar em outro computador Windows

Use Python 3.12 de 64 bits. Transfira o código pelo Git; recrie o ambiente em vez de
copiar os milhares de arquivos da `.venv`. Em uma instalação nova, no PowerShell:

```powershell
git clone --depth 1 https://github.com/susuque-samuel/VigiaAi.git
cd VigiaAi
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
.\.venv\Scripts\python.exe -m pip check
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
.\.venv\Scripts\python.exe main.py
```

Use um caminho sem acentos para o ambiente por compatibilidade com os recursos nativos
do MediaPipe. Complete o `.env` privadamente. Os índices de câmera variam por computador;
escolha o dispositivo no painel. Os pesos necessários já estão nos caminhos esperados:

| Arquivo | Função |
| --- | --- |
| `yolov8n.pt` | Pessoas. |
| `epi.pt` | Capacete, colete, óculos, luvas e máscara. |
| `runs/detect/treinamento_epi-2/weights/best.pt` | Segunda verificação de óculos. |

O ambiente local usado na integração tem Python 3.12.10 e PyTorch 2.6.0+cpu.
Uma instalação limpa em outro computador e CUDA não foram validadas nesta etapa.
`requirements-cuda.txt` é uma alternativa que exige GPU/driver compatíveis; não
instale sobre o ambiente funcional sem revisar as versões. `VIGIAAI_DEVICE=auto`
seleciona GPU disponível ou CPU; `cpu` força CPU.

## Política de EPI e alertas

Escolha os itens no painel, o tempo de confirmação e a regra de ausência:

| Regra | Comportamento |
| --- | --- |
| **Observação conservadora** (padrão) | Possíveis avisos após região visível, detalhe suficiente, reanálise e confirmação em vários quadros. É hipótese sujeita a falso alerta; exige verificação humana. |
| **Exigir classe explícita de ausência** | Exige detecção negativa, como `no_helmet`. Os pesos atuais só têm classes positivas e não produzirão avisos de ausência nesse modo. |

A política salva tem prioridade sobre os valores iniciais `EPI_MODO_AUSENCIA` e
`EPI_CONFIRMACAO_SEGUNDOS` do `.env`. São necessárias pelo menos três observações válidas;
o tempo configurado não garante aviso imediato.

A reanálise usa recortes de pessoa/cabeça, até quatro pessoas por rodada. Erro ou
pendência bloqueia possível ausência. Evidência fraca, pouca luz, perfil inadequado,
associação ambígua e detalhe pequeno aparecem como inconclusivos, com o motivo.
Isso não comprova pessoa equipada. Ampliar o recorte não recupera detalhe perdido;
óculos comuns/protetores ainda dependem de dados revisados e validação independente.

A análise temporal distingue transição suspeita, pessoa encontrada deitada/imóvel e
postura deitada persistente em baixa cadência. Esta última exige três observações e
pelo menos cinco segundos (ou confirmação maior configurada), sem afirmar que observou
queda ou imobilidade entre quadros espaçados. Perda da pessoa/pose e pausas excessivas
reiniciam a confirmação. São indicações visuais para verificação humana, sem diagnóstico.

**Câmera ao vivo:** Central e painel clássico respeitam o SMTP privado,
`NOTIFICACOES_ATIVAS=1` e `VIGIAAI_TESTE=0`. `SALVAR_IMAGEM_OCORRENCIA=0` permite
registro sem foto. Configure `SMTP_HOST`, `SMTP_PORTA`, `EMAIL_REMETENTE`,
`EMAIL_DESTINATARIO` e `SMTP_SENHA` (senha de aplicativo) no `.env`.

**Vídeos gravados:** não enviam e-mails nem salvam fotos de ocorrências, mesmo com
SMTP configurado. O evento mantém a indicação de simulação após trocar a fonte.
Os últimos 200 registros ficam em memória; exporte o JSON para guardá-los antes de
reiniciar. Os quadros não são enviados a serviços externos de IA.

## Backup e atualização

A versão anterior está na branch
[`codex/backup-antes-integracao-20261031`](https://github.com/susuque-samuel/VigiaAi/tree/codex/backup-antes-integracao-20261031).
Ela preserva o código anterior deste computador, incluindo alterações locais.
O commit publicado anterior `f8ef003` continua no histórico.

O backup privado local `VigiaAi-backup-20261031` contém também credenciais, dataset,
capturas e **1.345 fotos de amostras de EPI**, seus metadados e o RAR existente.
Esses dados e a `.venv` **não são publicados**. O histórico Git local antigo,
que rastreava o ambiente Python, fica guardado separadamente no backup privado.

Para atualizar um clone sem alterações de código pendentes, pare o servidor e execute
`git pull --ff-only`. As configurações e amostras ignoradas permanecem no computador.
Se houver mudanças manuais, preserve-as antes; não use descarte forçado.

Para consultar o código antigo em outro computador:

```powershell
git clone --branch codex/backup-antes-integracao-20261031 --single-branch https://github.com/susuque-samuel/VigiaAi.git VigiaAi-anterior
```

Reaproveite um ambiente compatível e suas configurações privadas para executar esse
backup. Ele não inclui fotos ou senhas; o sistema anterior usa a porta 5000 por padrão.
As instruções completas de restauração local ficam no `LEIA-ME.txt` do backup privado.

## Verificação e treinamento

A integração passou em **152 testes Python e 6 testes JavaScript**, com câmera e
SMTP simulados. A interface foi conferida no navegador. Os modelos reais também
processaram uma amostra local em três quadros, sem alterar a imagem. Isso verifica
execução, não mede precisão ou desempenho em campo. Câmera física e entrega real
de e-mail ainda precisam ser validadas na instalação.

```powershell
.\.venv\Scripts\python.exe tests/validar_integracao.py
$env:VIGIAAI_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:VIGIAAI_TESTE = '1'
$env:NOTIFICACOES_ATIVAS = '0'
node --test tests/test_painel.mjs tests/test_central.mjs tests/test_painel_oculos.mjs
```

Feche esse terminal de testes antes de voltar à operação normal: as variáveis acima
desativam notificações. O validador Python bloqueia SMTP real e dispositivos físicos.

`avaliar_eventos.py` separa queda/EPI, com filtro opcional `--tipo`; referências
antigas sem tipo significam queda. As amostras não foram rotuladas automaticamente
nem convertidas em treino. O dataset antigo sem teste independente pode ser recusado
pela auditoria nova; prepare uma divisão revisada antes de treinar.

Base da Central: `Livrinhos/VigiaA-i2.0`, branch `vigiaai-2.1-interface`, commit
`e5d9394a2b9f08a5c476bdbdb2cd1adff507e529`, reunida às correções locais de Samuel.
Os pesos publicados pelo amigo são os mesmos dos arquivos locais.

Detalhes e histórico: [Central](docs/CENTRAL_2_1.md), [IA](docs/APRIMORAMENTO_IA.md),
[monitoramento/coleta](MONITORAMENTO_E_COLETA.md), [treinamento](TREINAMENTO_EPI.md) e
[fontes de dados](docs/DATASETS_IA.md). Para esta atualização, este README tem prioridade
sobre os relatos antigos.
