"""Extract attachment text without executing uploaded content."""
import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.tsv', '.json', '.yaml', '.yml', '.xml', '.html', '.log', '.py', '.js', '.ts', '.java', '.sql', '.css', '.c', '.cpp', '.h', '.sh'}

def extract_file_text(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('文件大小不能超过 10MB')
    if suffix in TEXT_EXTENSIONS:
        for encoding in ('utf-8-sig', 'gb18030', 'utf-16'):
            try:
                text = data.decode(encoding)
                if '\x00' in text: continue
                break
            except UnicodeError: continue
        else: raise ValueError('无法识别文本编码，请转换为 UTF-8')
    elif suffix in {'.docx', '.xlsx', '.pptx'}:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                raise ValueError('文档解压后过大')
            names = sorted(archive.namelist())
            if suffix == '.docx': names = [n for n in names if n == 'word/document.xml']
            elif suffix == '.pptx': names = [n for n in names if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
            else: names = [n for n in names if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
            shared = []
            if suffix == '.xlsx' and 'xl/sharedStrings.xml' in archive.namelist():
                shared = [''.join(e.itertext()) for e in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
            parts = []
            for name in names:
                root = ET.fromstring(archive.read(name))
                if suffix == '.xlsx':
                    for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                        cells = []
                        for cell in row:
                            values = [e.text or '' for e in cell.iter() if e.tag.rsplit('}', 1)[-1] in {'v', 't'}]
                            value = ''.join(values)
                            if cell.get('t') == 's' and value: value = shared[int(value)]
                            cells.append(value)
                        parts.append('\t'.join(cells))
                else:
                    parts.extend(e.text or '' for e in root.iter() if e.tag.rsplit('}', 1)[-1] == 't')
            text = '\n'.join(parts)
    else:
        raise ValueError('暂不支持此文件格式。支持 PDF、图片、DOCX、XLSX、PPTX、文本和代码文件；旧版 Office 文件请另存为新格式')
    if not text.strip(): raise ValueError('文件没有可读取的文本内容')
    return text[:50000] + ('\n[附件内容超过限制，已截断]' if len(text) > 50000 else '')
