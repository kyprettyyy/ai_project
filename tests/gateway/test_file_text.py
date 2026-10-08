import io
import zipfile
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"services/gateway"))
from app.utils.file_text import extract_file_text

class FileTextTest(unittest.TestCase):
    def test_text_encodings_and_unsupported_binary(self):
        assert extract_file_text('中文'.encode('gb18030'), 'note.txt') == '中文'
        with self.assertRaisesRegex(ValueError, '暂不支持'):
            extract_file_text(b'PK', 'archive.zip')
    
    def test_docx_extracts_text(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="urn:word"><w:p><w:t>Hello</w:t></w:p></w:document>')
        assert extract_file_text(buf.getvalue(), 'sample.docx') == 'Hello'
    
    def test_xlsx_shared_strings(self):
        buf = io.BytesIO()
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('xl/sharedStrings.xml', '<sst><si><t>Name</t></si></sst>')
            z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{ns}"><sheetData><row><c t="s"><v>0</v></c><c><v>42</v></c></row></sheetData></worksheet>')
        assert extract_file_text(buf.getvalue(), 'sample.xlsx') == 'Name\t42'
