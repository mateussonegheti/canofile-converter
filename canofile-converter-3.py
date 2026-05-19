import os
import struct
import re
import csv
import img2pdf
import sys
from PIL import Image
from pathlib import Path
from io import BytesIO

# Novas dependências para OCR
try:
    import pytesseract
    from pypdf import PdfReader, PdfWriter
except ImportError:
    # Serão tratadas na inicialização dentro de verificar_tesseract()
    pass

# Ativa o suporte a cores ANSI no terminal do Windows
os.system("")

# Configurações de Cores e Estilos
class Cores:
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    CIANO = '\033[96m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'

def verificar_tesseract():
    """Verifica se o pytesseract e o executável do Tesseract estão disponíveis."""
    mensagem_erro = (
        f"{Cores.VERMELHO}╔══════════════════════════════════════════════════════╗\n"
        f"║                  ERRO DE DEPENDÊNCIA                 ║\n"
        f"╠══════════════════════════════════════════════════════╣\n"
        f"║ Certifique-se de instalar as bibliotecas do Python:  ║\n"
        f"║   pip install pytesseract pypdf                      ║\n"
        f"║                                                      ║\n"
        f"║ E de instalar o executável do Tesseract OCR:         ║\n"
        f"║   https://github.com/UB-Mannheim/tesseract/wiki      ║\n"
        f"║                                                      ║\n"
        f"║ (Se já instalado, verifique se ele está adicionado   ║\n"
        f"║ ao PATH do Windows ou configurado corretamente)      ║\n"
        f"╚══════════════════════════════════════════════════════╝{Cores.RESET}"
    )
    
    try:
        # 1. Verifica se a biblioteca foi instalada
        import pytesseract
        # 2. Verifica se o executável do Tesseract responde no sistema
        pytesseract.get_tesseract_version()
    except (NameError, ImportError):
        print(mensagem_erro)
        sys.exit(1)
    except Exception:
        print(mensagem_erro)
        sys.exit(1)

def exibir_boas_vindas():
    print(f"{Cores.CIANO}╔══════════════════════════════════════════════════════╗")
    print(f"║{Cores.NEGRITO}          CANOFILE → PDF CONVERTER            {Cores.RESET}{Cores.CIANO}║")
    print(f"║          Tribunal de Justiça — Setor de RH           ║")
    print(f"╠══════════════════════════════════════════════════════╣")
    print(f"║  Converte dossiês do sistema Canofile para PDF       ║")
    print(f"║  organizados por nome de servidor.                   ║")
    print(f"╠══════════════════════════════════════════════════════╣")
    print(f"║  Como usar:                                          ║")
    print(f"║  1. Informe a pasta de ORIGEM (ex: D:\\CF_SURF)       ║")
    print(f"║  2. Informe a pasta de DESTINO para os PDFs          ║")
    print(f"║  3. Escolha se quer simular antes (dry-run)          ║")
    print(f"║  4. Aguarde a conclusão                              ║")
    print(f"╠══════════════════════════════════════════════════════╣")
    print(f"║  OCR: ativo automaticamente via Tesseract            ║")
    print(f"║  Páginas com qualidade >= 60% recebem texto          ║")
    print(f"║  pesquisável. As demais ficam como imagem.           ║")
    print(f"╠══════════════════════════════════════════════════════╣")
    print(f"║  Dica: use dry-run primeiro para verificar se        ║")
    print(f"║  todos os arquivos estão sendo encontrados           ║")
    print(f"║  antes de gerar os PDFs de verdade.                  ║")
    print(f"╚══════════════════════════════════════════════════════╝{Cores.RESET}")

def exibir_etapa(titulo, sub, exemplo, num):
    print(f"\n  {Cores.CIANO}┌─ ETAPA {num} DE 3 ────────────────────────────────┐")
    print(f"  │  {Cores.NEGRITO}{titulo:<44}{Cores.RESET}{Cores.CIANO}  │")
    print(f"  │  {sub:<44}  │")
    print(f"  │  Exemplo: {exemplo:<35}  │")
    print(f"  └────────────────────────────────────────────────┘{Cores.RESET}")
    return input(f"  {Cores.VERDE}>{Cores.RESET} ").strip().strip('"')

def desenhar_barra(atual, total, largura=20):
    percent = atual / total if total > 0 else 0
    cheio = int(largura * percent)
    vazio = largura - cheio
    barra = "█" * cheio + "░" * vazio
    return f"{barra} {percent:>4.0%}"

# --- LÓGICA DE DECODIFICAÇÃO DBF E CANOFILE ---

def limpar_nome(nome_raw):
    nome = nome_raw.replace('@', '').strip()
    nome = re.sub(r'^\+', '', nome)
    nome = re.sub(r'\*\*apo\.$', '', nome, flags=re.IGNORECASE)
    nome = re.sub(r'[\\/*?:"<>|]', '_', nome)
    nome = "".join(char for char in nome if char.isprintable())
    return nome.strip() or "SEM_NOME"

def parse_dbf(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    num_records = struct.unpack_from('<I', data, 4)[0]
    header_size = struct.unpack_from('<H', data, 8)[0]
    record_size = struct.unpack_from('<H', data, 10)[0]
    fields = []
    offset = 32
    while data[offset] != 0x0D:
        fname = data[offset:offset+11].rstrip(b'\x00').decode('latin-1')
        flen = data[offset+16]
        fields.append((fname, flen))
        offset += 32
    records = []
    for i in range(num_records):
        start = header_size + i * record_size
        rec = data[start : start + record_size]
        if not rec or rec[0:1] == b'*': continue
        row, foff = {}, 1
        for fname, flen in fields:
            row[fname] = rec[foff:foff+flen]
            foff += flen
        records.append(row)
    return records

def get_tif_path(image_id, cabinet_path):
    if image_id <= 255:
        s2, local = 0, image_id
    else:
        s2 = image_id // 256
        local = image_id % 256
    rel_path = Path("00") / f"{s2:02X}" / f"{local:02X}.TIF"
    full_path = Path(cabinet_path) / rel_path
    if not full_path.exists():
        parent = Path(cabinet_path) / "00" / f"{s2:02X}"
        if parent.exists():
            for f in parent.iterdir():
                if f.name.upper() == f"{local:02X}.TIF": return f
    return full_path if full_path.exists() else None

def detect_cabinets(root):
    cabinets = []
    root_path = Path(root)
    if not root_path.exists(): return []
    for entry in sorted(os.listdir(root)):
        cab_path = root_path / entry
        if not cab_path.is_dir(): continue
        cab_dbf = pge_dbf = None
        for f in os.listdir(cab_path):
            if f.upper() == 'CF_CAB.DBF': cab_dbf = cab_path / f
            if f.upper() == 'CF_PGE.DBF': pge_dbf = cab_path / f
        if cab_dbf and pge_dbf:
            cabinets.append({'name': entry, 'path': cab_path, 'cab': cab_dbf, 'pge': pge_dbf})
    return cabinets

# --- FUNÇÕES DE OCR ---

def ocr_pagina(caminho_tif):
    """Aplica OCR em uma página individual caso a confiança seja satisfatória."""
    try:
        img = Image.open(caminho_tif)
        data = pytesseract.image_to_data(img, lang='por', output_type=pytesseract.Output.DICT)
        
        # Filtra valores válidos de confiança (maiores ou iguais a zero)
        confiancas = [float(c) for c in data['conf'] if c is not None and float(c) >= 0]
        
        media_conf = sum(confiancas) / len(confiancas) if confiancas else 0
        
        if media_conf >= 60:
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, lang='por', extension='pdf')
            return pdf_bytes, True
        else:
            return None, False
    except Exception:
        return None, False

def converter_com_ocr(tifs, pdf_path):
    """Processa a lista de TIFs aplicando OCR ou empacotando diretamente em PDF."""
    writer = PdfWriter()
    paginas_com_ocr = 0
    total_paginas = len(tifs)
    
    for tif in tifs:
        pdf_bytes, teve_ocr = ocr_pagina(tif)
        
        if teve_ocr:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
            paginas_com_ocr += 1
        else:
            # Sem OCR: Empacota com img2pdf
            try:
                img_pdf_bytes = img2pdf.convert(tif)
                reader = PdfReader(BytesIO(img_pdf_bytes))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception:
                # Fallback secundário com Pillow
                try:
                    img = Image.open(tif)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    buffer = BytesIO()
                    img.save(buffer, format="PDF")
                    buffer.seek(0)
                    reader = PdfReader(buffer)
                    for page in reader.pages:
                        writer.add_page(page)
                except Exception as e:
                    raise e

    with open(pdf_path, "wb") as f_pdf:
        writer.write(f_pdf)
        
    # Determinação do status final do OCR
    if paginas_com_ocr == total_paginas:
        return "Sim"
    elif paginas_com_ocr == 0:
        return "Não"
    else:
        return f"Parcial ({paginas_com_ocr} de {total_paginas} páginas)"

# --- VERIFICAÇÃO DE INTEGRIDADE ---

def verificar_pdf(pdf_path, paginas_esperadas):
    """
    Verifica a integridade de um PDF gerado.
    Retorna (status, detalhe):
      - ('OK', '')                  → tudo certo
      - ('CORROMPIDO', motivo)      → arquivo com problema
    """
    try:
        # 1. Arquivo existe e tem tamanho > 0
        tamanho = os.path.getsize(pdf_path)
        if tamanho == 0:
            return 'CORROMPIDO', 'Arquivo vazio (0 bytes)'

        # 2. Consegue abrir sem erro
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))

        # 3. Número de páginas > 0
        num_paginas = len(reader.pages)
        if num_paginas == 0:
            return 'CORROMPIDO', 'PDF sem páginas'

        # 4. Páginas batem com o esperado
        if num_paginas != paginas_esperadas:
            return 'DIVERGENTE', f'{num_paginas} páginas no PDF, {paginas_esperadas} esperadas'

        return 'OK', ''

    except Exception as e:
        return 'CORROMPIDO', f'Erro ao abrir: {str(e)[:60]}'


# --- FLUXO PRINCIPAL ---

def main():
    # Executa a validação de dependências do Tesseract
    verificar_tesseract()
    
    exibir_boas_vindas()
    
    origem = exibir_etapa("Pasta de ORIGEM", "Onde estão os gabinetes Canofile", "D:\\CF_SURF", 1)
    destino = exibir_etapa("Pasta de DESTINO", "Onde os PDFs serão salvos", "C:\\Users\\Dossies", 2)
    dry_mode = exibir_etapa("Modo simulação (dry-run)?", "S = Simular | N = Gerar PDFs", "N", 3)
    dry_run = dry_mode.upper() == 'S'

    gabs = detect_cabinets(origem)
    if not gabs:
        print(f"\n{Cores.VERMELHO}  [!] Nenhum gabinete válido encontrado na origem.{Cores.RESET}")
        return

    print(f"\n  {Cores.VERDE}┌─ CONFIRMAR CONFIGURAÇÕES ──────────────────────┐")
    print(f"  │  Origem  : {origem[:35]:<35} │")
    print(f"  │  Destino : {destino[:35]:<35} │")
    print(f"  │  Modo    : {('SIMULAÇÃO' if dry_run else 'CONVERSÃO REAL'):<35} │")
    print(f"  └────────────────────────────────────────────────┘{Cores.RESET}")
    input(f"  Pressione {Cores.NEGRITO}ENTER{Cores.RESET} para ler os gabinetes...")

    stats_pdfs = 0
    stats_pags = 0
    stats_erros = 0
    stats_ocr_sim = 0
    stats_ocr_parcial = 0
    stats_corrompidos = 0
    stats_divergentes = 0

    relatorio = []

    for g in gabs:
        cab_data = parse_dbf(g['cab'])
        pge_data = parse_dbf(g['pge'])

        contagem_nomes = {}
        lista_final_servidores = []
        for row in cab_data:
            idx_no = struct.unpack('<I', row['INDEX_NO'])[0]
            nome = limpar_nome(row['FIELD_1'].decode('latin-1').strip())
            
            # Garante que o nome seja único adicionando sufixo se duplicado
            nome_original = nome
            contador_dup = 1
            while nome in contagem_nomes:
                contador_dup += 1
                nome = f"{nome_original}_{contador_dup}"
            
            contagem_nomes[nome_original] = contagem_nomes.get(nome_original, 0) + 1
            lista_final_servidores.append((idx_no, nome, nome_original))

        # Cabeçalho do Gabinete
        print(f"\n  {Cores.CIANO}╔══════════════════════════════════════════════════╗")
        print(f"  ║  Gabinete: {g['name']:<36} ║")
        print(f"  ║  Servidores: {len(lista_final_servidores):<6} |  Páginas: {len(pge_data):<10}      ║")
        print(f"  ╚══════════════════════════════════════════════════╝{Cores.RESET}")

        # Listagem de Servidores
        print(f"  Servidores identificados:")
        print(f"  ┌─────┬────────────────────────────────────────────┐")
        for i, (idx, nome, nome_orig) in enumerate(lista_final_servidores, 1):
            aviso = ""
            cor_nome = Cores.RESET
            if contagem_nomes[nome_orig] > 1:
                aviso = f" {Cores.AMARELO}(DUPLICADO){Cores.RESET}"
                cor_nome = Cores.AMARELO
            
            print(f"  │ {idx:<3} │ {cor_nome}{nome[:42]:<42}{Cores.RESET} │{aviso}")
        print(f"  └─────┴────────────────────────────────────────────┘")
        
        input(f"\n  Pressione {Cores.NEGRITO}ENTER{Cores.RESET} para iniciar este gabinete ou Ctrl+C para sair...")

        # Mapeamento de páginas
        mapa_paginas = {}
        for r in pge_data:
            try:
                idx_ref = int(r['INDEX_NUM'].decode('latin-1').strip())
                pg_num = int(r['PAGE'].decode('latin-1').strip() or 0)
                side = r['SIDE'].decode('latin-1').strip() or 'A'
                img_id = struct.unpack('<I', r['IMAGE_ID'])[0]
                if idx_ref not in mapa_paginas: mapa_paginas[idx_ref] = []
                mapa_paginas[idx_ref].append({'pg': pg_num, 'side': side, 'img': img_id})
            except: continue

        cab_out = Path(destino) / g['name']
        if not dry_run: cab_out.mkdir(parents=True, exist_ok=True)

        total_serv = len(lista_final_servidores)
        for i, (idx_no, nome, nome_orig) in enumerate(lista_final_servidores, 1):
            pags = sorted(mapa_paginas.get(idx_no, []), key=lambda x: (x['pg'], x['side']))
            tifs = [str(get_tif_path(p['img'], g['path'])) for p in pags if get_tif_path(p['img'], g['path'])]

            # Interface de progresso
            barra = desenhar_barra(i, total_serv)
            cor_status = Cores.AMARELO if dry_run else Cores.VERDE
            sys.stdout.write(f"\r  [{i:03d}/{total_serv:03d}]  {barra}  {nome[:25]:<25}")
            sys.stdout.flush()

            status_pdf = "Sem imagens"
            status_ocr = "-"
            verificacao = "-"
            observacao = ""

            if tifs:
                if not dry_run:
                    pdf_path = cab_out / f"{nome}.pdf"
                    try:
                        status_ocr = converter_com_ocr(tifs, pdf_path)
                        stats_pdfs += 1
                        stats_pags += len(tifs)
                        status_pdf = "Sim"
                        if status_ocr == "Sim":
                            stats_ocr_sim += 1
                        elif "Parcial" in str(status_ocr):
                            stats_ocr_parcial += 1
                    except Exception:
                        stats_erros += 1
                        status_pdf = "Erro"
                        status_ocr = "Erro"
                        observacao = "Erro ao compilar as imagens em PDF"
                else:
                    stats_pdfs += 1
                    stats_pags += len(tifs)
                    status_pdf = "Sim (Simulação)"
                    status_ocr = "-"
                    observacao = "Modo de simulação (dry-run)"
            else:
                observacao = "Nenhuma imagem localizada na subpasta do Canofile"

            relatorio.append({
                "Gabinete":    g['name'],
                "Nº":          idx_no,
                "Nome":        nome,
                "Páginas":     len(tifs),
                "PDF Gerado":  status_pdf,
                "OCR":         status_ocr,
                "Verificação": verificacao,
                "Observação":  observacao,
            })

    # --- Verificação de integridade em lote ---
    if not dry_run:
        print(f"\n  {Cores.CIANO}╔══════════════════════════════════════════════════╗")
        print(f"  ║  Verificando integridade dos PDFs gerados...     ║")
        print(f"  ╚══════════════════════════════════════════════════╝{Cores.RESET}")

        total_verificar = sum(1 for r in relatorio if r["PDF Gerado"] == "Sim")
        verificados = 0

        for linha in relatorio:
            if linha["PDF Gerado"] != "Sim":
                linha["Verificação"] = "-"
                continue

            cab_out = Path(destino) / linha["Gabinete"]
            pdf_path_check = cab_out / f"{linha['Nome']}.pdf"

            ver_status, ver_detalhe = verificar_pdf(str(pdf_path_check), linha["Páginas"])
            linha["Verificação"] = ver_status if not ver_detalhe else f"{ver_status}: {ver_detalhe}"

            if ver_status == 'CORROMPIDO':
                stats_corrompidos += 1
            elif ver_status == 'DIVERGENTE':
                stats_divergentes += 1

            verificados += 1
            barra = desenhar_barra(verificados, total_verificar)
            sys.stdout.write(f"\r  [{verificados:04d}/{total_verificar:04d}]  {barra}  {linha['Nome'][:25]:<25}")
            sys.stdout.flush()

        print(f"\n  {Cores.VERDE}✓  Verificação concluída.{Cores.RESET}")
    else:
        for linha in relatorio:
            linha["Verificação"] = "-"

    # --- Gerar CSV ---
    Path(destino).mkdir(parents=True, exist_ok=True)
    csv_path = Path(destino) / "relatorio_conversao.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Gabinete", "Nº", "Nome", "Páginas", "PDF Gerado", "OCR", "Verificação", "Observação"])
        writer.writeheader()
        writer.writerows(relatorio)

    # --- Resumo Final ---
    print(f"\n\\n  {Cores.VERDE}╔══════════════════════════════════════════════════╗")
    print(f"  ║  CONVERSÃO CONCLUÍDA                             ║")
    print(f"  ╠══════════════════════════════════════════════════╣")
    print(f"  ║  PDFs {'process.' if dry_run else 'gerados '} :  {stats_pdfs:<30} ║")
    print(f"  ║  Total páginas :  {stats_pags:<30} ║")
    print(f"  ║  Erros/Faltas  :  {stats_erros:<30} ║")
    print(f"  ║  OCR completo  :  {stats_ocr_sim:<30} ║")
    print(f"  ║  OCR parcial   :  {stats_ocr_parcial:<30} ║")
    cor_corr = Cores.VERMELHO if stats_corrompidos > 0 else Cores.VERDE
    cor_div  = Cores.AMARELO  if stats_divergentes > 0 else Cores.VERDE
    print(f"  ║  {cor_corr}Corrompidos    :  {stats_corrompidos:<30}{Cores.VERDE} ║")
    print(f"  ║  {cor_div}Divergentes    :  {stats_divergentes:<30}{Cores.VERDE} ║")
    print(f"  ║  Relatório CSV :  relatorio_conversao.csv        ║")
    print(f"  ║  Pasta de saída:  {str(destino)[:28]:<28}... ║")
    print(f"  ╚══════════════════════════════════════════════════╝{Cores.RESET}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Cores.VERMELHO}  Operação cancelada pelo usuário.{Cores.RESET}")
    except Exception as e:
        print(f"\n\n{Cores.VERMELHO}  ERRO CRÍTICO: {e}{Cores.RESET}")
