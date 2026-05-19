# Canofile → PDF Converter

Ferramenta de conversão de acervos digitalizados do sistema legado **Canofile** (Canon, década de 1990) para arquivos PDF organizados por chave de indexação.

---

## Contexto

O Canofile era um sistema de arquivamento eletrônico da Canon utilizado para digitalizar e organizar documentos em discos ópticos (formato EMO). Com a desativação do sistema, os arquivos TIFF das imagens ficaram armazenados em pastas com nomes em código hexadecimal, sem nenhuma indicação visível de a qual registro pertencem.

Este script realiza a **engenharia reversa** dos arquivos de índice do Canofile (`CF_CAB.DBF` e `CF_PGE.DBF`) para reconstruir o vínculo entre cada imagem digitalizada e sua chave de indexação, gerando um PDF por registro com todas as páginas na ordem correta.

---

## Funcionalidades

- Detecção automática de todos os gabinetes (subpastas `CABxV2`) na pasta de origem
- Leitura dos arquivos DBF proprietários do Canofile com decodificação correta de campos binários
- Conversão das imagens TIFF para PDF, um por chave de indexação
- **OCR automático** via Tesseract — páginas com qualidade de scan ≥ 60% recebem camada de texto pesquisável; as demais são empacotadas como imagem pura
- Suporte a **Tesseract portable** — basta colocar a pasta `tesseract/` ao lado do script, sem necessidade de instalação ou permissões administrativas
- Tratamento de chaves duplicadas — registros com o mesmo nome recebem sufixo `_2`, `_3`, etc.
- **Verificação de integridade em lote** após a conversão — verifica tamanho, abertura e número de páginas de cada PDF gerado
- Geração de **relatório CSV** completo ao final, compatível com Excel (UTF-8 com BOM)
- Modo **dry-run** para simular a conversão sem gerar nenhum arquivo
- Interface visual no terminal com barra de progresso e cores ANSI

---

## Estrutura esperada dos arquivos Canofile

```
CF_SURF/
├── CAB1V2/
│   ├── CF_CAB.DBF       ← índice de registros
│   ├── CF_PGE.DBF       ← índice de páginas → imagens
│   └── 00/
│       ├── 00/          ← IMAGE_IDs 1–255
│       │   ├── 01.TIF
│       │   └── ...
│       ├── 01/          ← IMAGE_IDs 256–511
│       └── ...
└── CAB2V2/
    └── ...              ← mesma estrutura
```

---

## Pré-requisitos

### Python
Testado com **Python 3.10+**. Funciona com instalação padrão ou versão portable.

### Bibliotecas Python

```bash
python -m pip install Pillow img2pdf pytesseract pypdf
```

### Tesseract OCR

**Opção 1 — Instalação padrão (requer permissão de administrador):**

Baixe o instalador em: https://github.com/UB-Mannheim/tesseract/wiki  
Durante a instalação, marque o pacote de idioma desejado (ex: **Portuguese**).

**Opção 2 — Portable (sem instalação, recomendado para ambientes corporativos):**

1. Extraia os arquivos do instalador do Tesseract em uma pasta chamada `tesseract/` ao lado do script
2. Baixe o arquivo de idioma e coloque em `tesseract/tessdata/`:
   - `por.traineddata` → https://github.com/tesseract-ocr/tessdata/blob/main/por.traineddata

Estrutura final:

```
Python/
├── python.exe
├── canofile-converter-3.py
└── tesseract/
    ├── tesseract.exe
    ├── libtesseract-5.dll
    ├── (demais DLLs...)
    └── tessdata/
        └── por.traineddata
```

O script detecta automaticamente a pasta `tesseract/` ao lado dele, sem necessidade de configurar o PATH do Windows.

---

## Como usar

```bash
python canofile-converter-3.py
```

O script é interativo e guia o usuário em 3 etapas:

```
┌─ ETAPA 1 DE 3 ────────────────────────────────┐
│  Pasta de ORIGEM                               │
│  Onde estão os gabinetes Canofile              │
│  Exemplo: D:\CF_SURF                           │
└────────────────────────────────────────────────┘
> D:\CF_SURF

┌─ ETAPA 2 DE 3 ────────────────────────────────┐
│  Pasta de DESTINO                              │
│  Onde os PDFs serão salvos                     │
│  Exemplo: C:\Users\usuario\Desktop\PDFs        │
└────────────────────────────────────────────────┘
> C:\Users\usuario\Desktop\PDFs

┌─ ETAPA 3 DE 3 ────────────────────────────────┐
│  Modo simulação (dry-run)?                     │
│  S = Simular | N = Gerar PDFs                  │
│  Exemplo: N                                    │
└────────────────────────────────────────────────┘
> N
```

**Dica:** use `S` no dry-run primeiro para verificar se todos os gabinetes e imagens estão sendo encontrados antes de iniciar a conversão real.

---

## Saída

### Estrutura de pastas dos PDFs

A estrutura original dos gabinetes é preservada na pasta de destino:

```
PDFs/
├── CAB1V2/
│   ├── CHAVE DE INDEXACAO 001.pdf
│   ├── CHAVE DE INDEXACAO 002.pdf
│   └── ...
└── CAB2V2/
    ├── CHAVE DE INDEXACAO 003.pdf
    └── ...
```

### Relatório CSV

Ao final da execução, o arquivo `relatorio_conversao.csv` é gerado na pasta de destino com as seguintes colunas:

| Coluna | Descrição |
|---|---|
| Gabinete | Nome do gabinete (CAB1V2, CAB2V2, etc.) |
| Nº | INDEX_NO do registro no DBF |
| Nome | Chave de indexação conforme lida no Canofile |
| Páginas | Quantidade de imagens mapeadas |
| PDF Gerado | `Sim`, `Não`, `Erro` ou `Sem imagens` |
| OCR | `Sim`, `Não`, `Parcial (X de Y páginas)` ou `-` |
| Verificação | `OK`, `CORROMPIDO: motivo` ou `DIVERGENTE: motivo` |
| Observação | Informações adicionais (duplicados, erros, etc.) |

---

## Fluxo de execução

```
1. Verificação do Tesseract
         ↓
2. Coleta de informações (origem, destino, dry-run)
         ↓
3. Detecção automática dos gabinetes
         ↓
4. Para cada gabinete:
   a. Listagem dos registros identificados (com marcação de duplicados)
   b. Conversão TIFF → PDF com OCR página a página
         ↓
5. Verificação de integridade em lote (todos os PDFs de uma vez)
         ↓
6. Geração do relatório CSV
         ↓
7. Exibição do resumo final
```

---

## Engenharia reversa do formato Canofile

O formato proprietário do Canofile foi decifrado por análise dos arquivos binários. Os pontos mais relevantes:

**CF_CAB.DBF** — os campos `INDEX_NO` (4 bytes) e `PGE_CNT` (2 bytes) são inteiros binários little-endian, ao contrário do padrão dBase que os declara como texto. A chave de indexação fica no campo `FIELD_1` em encoding latin-1.

**CF_PGE.DBF** — o campo `IMAGE_ID` (4 bytes little-endian) é um contador sequencial global que mapeia para o caminho do TIFF usando a seguinte fórmula:

```python
if image_id <= 255:
    subpasta, arquivo = 0, image_id
else:
    subpasta = image_id // 256
    arquivo  = image_id % 256

caminho = f"CABxV2/00/{subpasta:02X}/{arquivo:02X}.TIF"
```

**CF_IMG.BIN** e **CF_IDX.BIN** — bitmaps de controle onde cada bit representa um slot em uso (imagens e índices respectivamente).

---

## Licença

MIT License — livre para uso, modificação e distribuição.

---

## Contribuições

Este projeto foi desenvolvido para migração de acervos digitalizados em sistemas Canofile legados, mas a lógica de decodificação dos arquivos pode ser útil para qualquer instituição que precise converter documentos desse formato.

Pull requests são bem-vindos, especialmente para:
- Suporte a outros formatos de saída (TIFF multipágina, PDF/A)
- Interface gráfica
- Suporte a outros idiomas no OCR
- Suporte a outros campos de indexação do CF_CAB.DBF
