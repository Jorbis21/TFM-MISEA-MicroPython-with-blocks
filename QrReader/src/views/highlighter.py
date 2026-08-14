from PyQt6.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import QRegularExpression

class PythonHighlighter(QSyntaxHighlighter):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.style_rules = []
        self._configure_rules()

    def _configure_rules(self):
        """Configura las reglas de estilo del highlighter"""
        """Configure the style rules of the highlighter"""
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#F44747"))
        error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        error_format.setUnderlineColor(QColor("#F44747"))
        self.style_rules.append((QRegularExpression(r'# ERROR.*'), error_format))

        flow_format = QTextCharFormat()
        flow_format.setForeground(QColor("#C586C0"))
        flow_words = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bwhile\b', 
                         r'\bfor\b', r'\bin\b', r'\bbreak\b', r'\bcontinue\b', r'\breturn\b']
        for w in flow_words:
            self.style_rules.append((QRegularExpression(w), flow_format))

        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#569CD6"))
        kw_words = [r'\bfrom\b', r'\bimport\b', r'\bdef\b', r'\bclass\b', r'\bpass\b', r'\bglobal\b', r'\bas\b']
        for w in kw_words:
            self.style_rules.append((QRegularExpression(w), kw_format))

        bool_format = QTextCharFormat()
        bool_format.setForeground(QColor("#569CD6"))
        for w in [r'\bTrue\b', r'\bFalse\b', r'\bNone\b']:
            self.style_rules.append((QRegularExpression(w), bool_format))

        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#DCDCAA"))
        self.style_rules.append((QRegularExpression(r'\b[a-zA-Z_]\w*(?=\()'), func_format))

        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#B5CEA8"))
        self.style_rules.append((QRegularExpression(r'\b\d+\.?\d*\b'), num_format))

        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#CE9178"))
        self.style_rules.append((QRegularExpression(r'".*?"'), str_format))
        self.style_rules.append((QRegularExpression(r"'.*?'"), str_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.style_rules.append((QRegularExpression(r'#(?!\s*ERROR).*'), comment_format))

    def highlightBlock(self, text):
        """Pinta las palabras"""
        """Paint the words"""
        for expresion, format in self.style_rules:
            match_iterator = expresion.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)