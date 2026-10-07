# Simulador de redes de filas

Simulador de eventos discretos desenvolvido em Python para a atividade de
Simulação e Métodos Analíticos. Ele aceita redes com qualquer quantidade de
filas e usa o mesmo formato YAML do simulador de referência do módulo 3.

## Requisitos

- Python 3.10 ou superior;
- `pip`;
- Java (opcional, necessário somente para os testes diferenciais completos).

## Instalação

Na raiz do projeto, crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell, a ativação é feita com:

```powershell
.venv\Scripts\Activate.ps1
```

Instale a dependência do projeto:

```bash
python -m pip install -r requirements.txt
```

## Como executar

Execute o modelo incluído no projeto:

```bash
python main.py models/atividade.yml
```

Para gerar uma saída em JSON:

```bash
python main.py models/atividade.yml --json
```

Para salvar o relatório em um arquivo:

```bash
python main.py models/atividade.yml > resultado.txt
```

Outro modelo compatível pode ser informado no lugar de
`models/atividade.yml`.

## Testes

Testes do simulador Python, sem exigir Java:

```bash
python -m unittest tests.test_simulator -v
```

Suíte completa, incluindo a comparação com o simulador Java de referência:

```bash
python -m unittest discover -s tests -v
```

Os testes diferenciais executam os mesmos cenários no código Python e no
`modulo3/simulator.jar`, comparando tempo global, perdas, tempos por estado e
probabilidades. O JAR faz parte da validação do projeto e deve ser mantido.

## Formato do modelo

- `arrivals`: instante da primeira chegada externa em cada fila de entrada;
- `queues`: servidores, capacidade e intervalos uniformes de chegada e serviço;
- `network`: rotas internas e suas probabilidades;
- `rndnumbers`: sequência explícita de números pseudoaleatórios; ou
- `seeds` e `rndnumbersPerSeed`: sementes e quantidade de números por semente.

Se as probabilidades das rotas de uma fila somarem menos que `1`, a diferença
representa a probabilidade de o cliente sair do sistema. Uma fila sem
`capacity` tem capacidade infinita. Quando `seeds` está presente, `rndnumbers`
é ignorado, assim como no simulador do módulo 3.

## Estrutura do projeto

```text
main.py                 Interface de linha de comando
models/atividade.yml    Modelo principal da atividade
simulator/              Leitura, motor e relatório da simulação
tests/                  Testes unitários e diferenciais
modulo3/                Simulador Java e modelo usados como referência
requirements.txt        Dependências Python
T1_ARQUIVO_...docx      Formulário oficial de entrega da atividade
```
