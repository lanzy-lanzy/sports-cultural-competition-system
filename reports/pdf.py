"""ReportLab PDF renderer for official Competrack reports.

The renderer is intentionally data-driven: it receives a
:class:`reports.reporting.ReportData` and produces a formally styled PDF with
an institutional header, document-control block, summary strip, repeated table
headers, and numbered pages.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .reporting import ReportData, ReportSection

PINE = colors.HexColor('#116B3B')
PINE_DEEP = colors.HexColor('#0C5330')
PINE_DARK = colors.HexColor('#0B3A20')
INK = colors.HexColor('#15251B')
SLATE = colors.HexColor('#5B6B60')
MUTED = colors.HexColor('#7C8B80')
MOSS = colors.HexColor('#EAF2EB')
PAPER = colors.HexColor('#F5F7F4')
LINE = colors.HexColor('#D8E4DA')
GOLD = colors.HexColor('#B08A2E')
WHITE = colors.white


class _NumberedCanvas(canvas.Canvas):
    """Canvas that adds a footer with an accurate page count."""

    def __init__(self, *args, report: ReportData = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._report = report
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total_pages):
        report = self._report
        width, _ = landscape(A4)
        y = 10 * mm
        self.saveState()
        self.setStrokeColor(LINE)
        self.setLineWidth(0.6)
        self.line(16 * mm, y + 4 * mm, width - 16 * mm, y + 4 * mm)
        self.setFillColor(MUTED)
        self.setFont('Helvetica', 7)
        generated = report.generated_at.strftime('%B %d, %Y at %I:%M %p') if report else ''
        self.drawString(16 * mm, y, f'Generated {generated} · Competrack')
        self.drawCentredString(
            width / 2, y, 'Official document · J.H. Cerilles State College',
        )
        self.setFillColor(PINE_DEEP)
        self.setFont('Helvetica-Bold', 7)
        self.drawRightString(width - 16 * mm, y, f'Page {self._pageNumber} of {total_pages}')
        self.restoreState()


def _draw_page_header(report: ReportData):
    width, height = landscape(A4)

    def draw(c, doc):
        c.saveState()
        c.setFillColor(PINE_DARK)
        c.rect(0, height - 17 * mm, width, 17 * mm, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(0, height - 17 * mm, width, 1.2 * mm, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 10.5)
        c.drawString(16 * mm, height - 9.5 * mm, 'J.H. CERILLES STATE COLLEGE')
        c.setFont('Helvetica', 7.5)
        c.setFillColor(colors.HexColor('#CFE3D5'))
        c.drawString(16 * mm, height - 13.7 * mm, 'Competrack · Competition Management Platform')

        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawRightString(width - 16 * mm, height - 9.5 * mm, report.title.upper()[:78])
        c.setFillColor(colors.HexColor('#CFE3D5'))
        c.setFont('Helvetica', 7.5)
        c.drawRightString(width - 16 * mm, height - 13.7 * mm, 'OFFICIAL REPORT')
        c.restoreState()

    return draw


def _build_styles():
    styles = getSampleStyleSheet()
    return {
        'eyebrow': ParagraphStyle(
            'ReportEyebrow', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=7.5, leading=9, textColor=GOLD, spaceAfter=3,
        ),
        'title': ParagraphStyle(
            'ReportTitle', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=21, leading=24, textColor=PINE_DARK, spaceAfter=3,
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle', parent=styles['Normal'], fontName='Helvetica',
            fontSize=8.8, leading=12, textColor=SLATE,
        ),
        'competition': ParagraphStyle(
            'ReportCompetition', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=8.5, leading=11, textColor=PINE_DEEP, spaceBefore=4,
        ),
        'meta_label': ParagraphStyle(
            'MetaLabel', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=6.4, leading=8, textColor=MUTED,
        ),
        'meta_value': ParagraphStyle(
            'MetaValue', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=8.6, leading=10.5, textColor=INK,
        ),
        'section': ParagraphStyle(
            'SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=10.5, leading=13, textColor=PINE_DARK, spaceBefore=6, spaceAfter=5,
        ),
        'head': ParagraphStyle(
            'TableHead', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=7, leading=8.5, textColor=WHITE,
        ),
        'head_right': ParagraphStyle(
            'TableHeadRight', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=7, leading=8.5, textColor=WHITE, alignment=TA_RIGHT,
        ),
        'cell': ParagraphStyle(
            'TableCell', parent=styles['Normal'], fontName='Helvetica',
            fontSize=7.6, leading=9.5, textColor=INK,
        ),
        'cell_right': ParagraphStyle(
            'TableCellRight', parent=styles['Normal'], fontName='Helvetica',
            fontSize=7.6, leading=9.5, textColor=INK, alignment=TA_RIGHT,
        ),
        'empty': ParagraphStyle(
            'EmptySection', parent=styles['Normal'], fontName='Helvetica-Oblique',
            fontSize=8, leading=10, textColor=MUTED,
        ),
        'note': ParagraphStyle(
            'ReportNote', parent=styles['Normal'], fontName='Helvetica',
            fontSize=7, leading=9, textColor=MUTED, alignment=TA_CENTER,
        ),
        'sign_label': ParagraphStyle(
            'SignLabel', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=7, leading=9, textColor=SLATE,
        ),
        'sign_caption': ParagraphStyle(
            'SignCaption', parent=styles['Normal'], fontName='Helvetica',
            fontSize=6.8, leading=8.5, textColor=MUTED,
        ),
    }


def _control_box(report: ReportData, styles, width=190):
    key = report.key.upper().replace('-', '')[:10]
    reference = f'{key}-{report.generated_at.strftime("%Y%m%d-%H%M")}'
    generated = report.generated_at.strftime('%B %d, %Y')
    generated_time = report.generated_at.strftime('%I:%M %p')
    reference_style = ParagraphStyle(
        'ReferenceValue', parent=styles['meta_value'], fontSize=6.6, leading=8.5,
        textColor=PINE_DEEP,
    )
    data = [
        [Paragraph('DOCUMENT CONTROL', styles['meta_label']), ''],
        [Paragraph('Generated', styles['meta_label']),
         Paragraph(f'{generated}<br/>{generated_time}', styles['meta_value'])],
        [Paragraph('Records', styles['meta_label']),
         Paragraph(str(report.record_count), styles['meta_value'])],
        [Paragraph('Reference', styles['meta_label']),
         Paragraph(reference, reference_style)],
    ]
    box = Table(data, colWidths=[52, width - 52])
    box.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, -1), PAPER),
        ('BOX', (0, 0), (-1, -1), 0.6, LINE),
        ('LINEBEFORE', (0, 0), (0, -1), 2.4, PINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 7),
    ]))
    return box


def _summary_tables(report: ReportData, styles, width):
    """Render summary metrics in compact institutional cards."""
    if not report.summary:
        return []
    chunk_size = 4
    tables = []
    items = report.summary
    for start in range(0, len(items), chunk_size):
        chunk = items[start:start + chunk_size]
        labels = [Paragraph(escape(label.upper()), styles['meta_label']) for label, _ in chunk]
        values = [Paragraph(escape(str(value)), styles['meta_value']) for _, value in chunk]
        table = Table([labels, values], colWidths=[width / len(chunk)] * len(chunk))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), MOSS),
            ('BOX', (0, 0), (-1, -1), 0.6, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.6, WHITE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('TOPPADDING', (0, 1), (-1, 1), 1),
        ]))
        tables.append(table)
    return tables


def _column_widths(section: ReportSection, available):
    weights = []
    for index, column in enumerate(section.columns):
        samples = [column]
        for row in section.rows[:80]:
            if index < len(row):
                samples.append(row[index])
        longest = max((len(str(value)) for value in samples), default=6)
        weight = max(6, min(longest, 30))
        if index in section.numeric_columns:
            weight = min(weight, 7)
        if any(token in column.lower() for token in ('date', 'start', 'end', 'submitted', 'reviewed at', 'scored at', 'registered')):
            weight = min(max(weight, 10), 16)
        weights.append(weight)
    total = sum(weights) or 1
    widths = [available * weight / total for weight in weights]
    # Never let a column collapse below a readable minimum; borrow from the widest.
    minimum = 27
    shortfall = sum(max(0, minimum - width) for width in widths)
    if shortfall:
        widths = [max(width, minimum) for width in widths]
        overflow = sum(widths) - available
        if overflow > 0:
            adjustable = [i for i, width in enumerate(widths) if width > minimum]
            extra = sum(widths[i] - minimum for i in adjustable) or 1
            for i in adjustable:
                widths[i] -= overflow * (widths[i] - minimum) / extra
    return widths


def _data_table(section: ReportSection, styles, available):
    header = [
        Paragraph(
            escape(column),
            styles['head_right'] if index in section.numeric_columns else styles['head'],
        )
        for index, column in enumerate(section.columns)
    ]
    data = [header]
    for row in section.rows:
        rendered = []
        for index, value in enumerate(row):
            text = escape(str(value)) if value not in (None, '') else '&mdash;'
            style = styles['cell_right'] if index in section.numeric_columns else styles['cell']
            rendered.append(Paragraph(text, style))
        data.append(rendered)

    table = Table(
        data,
        colWidths=_column_widths(section, available),
        repeatRows=1,
        hAlign='LEFT',
        splitByRow=1,
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PINE),
        ('BOX', (0, 0), (-1, -1), 0.8, PINE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.9, PINE_DEEP),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PAPER]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4.5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    return table


def _sign_off(styles, width):
    signatures = Table(
        [
            [Paragraph('Prepared by', styles['sign_label']),
             Paragraph('Certified correct by', styles['sign_label'])],
            ['', ''],
        ],
        colWidths=[width / 2, width / 2],
        rowHeights=[None, 26],
    )
    signatures.setStyle(TableStyle([
        ('LINEBELOW', (0, 1), (0, 1), 0.8, SLATE),
        ('LINEBELOW', (1, 1), (1, 1), 0.8, SLATE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 20),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
    ]))
    captions = Table(
        [[Paragraph('Competition Management Office', styles['sign_caption']),
          Paragraph('Competition Chairperson', styles['sign_caption'])]],
        colWidths=[width / 2, width / 2],
    )
    captions.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 20),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    return [signatures, captions]


def build_report_pdf(report: ReportData) -> bytes:
    """Render *report* and return the PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=29 * mm,
        bottomMargin=17 * mm,
        title=report.title,
        author='J.H. Cerilles State College · Competrack',
        subject=report.subtitle,
        creator='Competrack Competition Management Platform',
    )
    styles = _build_styles()
    available = doc.width
    story = []

    left = [
        Paragraph('OFFICIAL COMPETITION REPORT', styles['eyebrow']),
        Paragraph(escape(report.title), styles['title']),
        Paragraph(escape(report.subtitle), styles['subtitle']),
    ]
    if report.competition:
        start = report.competition.start_date.strftime('%B %d, %Y')
        end = report.competition.end_date.strftime('%B %d, %Y')
        left.append(Paragraph(
            f"{escape(report.competition.name)} &nbsp;·&nbsp; {start} &ndash; {end}",
            styles['competition'],
        ))

    cover = Table(
        [[left, _control_box(report, styles)]],
        colWidths=[available - 200, 190],
    )
    cover.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 14),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(cover)
    story.append(Spacer(1, 7))
    story.append(HRFlowable(width='100%', thickness=1.4, color=PINE, spaceBefore=0, spaceAfter=8))

    for table in _summary_tables(report, styles, available):
        story.append(table)
        story.append(Spacer(1, 5))

    if report.sections:
        story.append(Spacer(1, 3))

    for index, section in enumerate(report.sections):
        heading = section.title or f'Report data{" " + str(index + 1) if len(report.sections) > 1 else ""}'
        story.append(Paragraph(
            f'<font color="#116B3B">&#9632;</font>&nbsp;&nbsp;{escape(heading)}',
            styles['section'],
        ))
        if section.rows:
            story.append(_data_table(section, styles, available))
        else:
            story.append(Paragraph(escape(section.empty_message), styles['empty']))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 2))
    sign_off = [
        HRFlowable(width='100%', thickness=0.7, color=LINE, spaceBefore=2, spaceAfter=6),
        Paragraph('CERTIFICATION', ParagraphStyle(
            'Certification', parent=styles['meta_label'], textColor=PINE_DEEP,
            fontSize=7, leading=9, spaceAfter=2,
        )),
    ]
    sign_off.extend(_sign_off(styles, available))
    story.extend(sign_off)

    doc.build(
        story,
        onFirstPage=_draw_page_header(report),
        onLaterPages=_draw_page_header(report),
        canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, report=report, **kwargs),
    )
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
