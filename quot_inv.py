import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget,
                             QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QMessageBox, QDateEdit, QComboBox, QSpinBox,
                             QDoubleSpinBox, QHeaderView, QDialog, QFormLayout,
                             QDialogButtonBox, QGroupBox, QGridLayout, QFileDialog,
                              QProgressDialog, QCheckBox, QScrollArea)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QIcon
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus.flowables import HRFlowable
import os
import tempfile
import subprocess
import textwrap
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('business.db')
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Customers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                address TEXT,
                email TEXT,
                phone TEXT
            )
        ''')
        
        # Company settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                address TEXT,
                phone TEXT,
                email TEXT,
                website TEXT,
                logo_path TEXT,
                smtp_server TEXT,
                smtp_port TEXT,
                smtp_username TEXT,
                smtp_password TEXT
            )
        ''')
        
        # Add SMTP columns for existing databases
        for col in ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password']:
            try:
                cursor.execute(f"ALTER TABLE company_settings ADD COLUMN {col} TEXT")
            except:
                pass
        
        # Insert default company settings if not exists
        cursor.execute("SELECT COUNT(*) FROM company_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO company_settings (company_name, address, phone, email, website)
                VALUES (?, ?, ?, ?, ?)
            ''', ("AD DEEN Engineering", "No.21, Jalan Pantun 1, U2/3a\nTTDI Jaya, 40150 Shah Alam, Selangor", 
                  "(+60193838699", "honda8161@yahoo.com.my", "www.ad-deen-engineering.com"))
        
        # Quotations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER,
                date TEXT NOT NULL,
                valid_until TEXT,
                status TEXT DEFAULT 'Draft',
                notes TEXT,
                subtotal REAL DEFAULT 0,
                tax_rate REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                discount REAL DEFAULT 0,
                total REAL DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Quotation items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quotation_id INTEGER,
                description TEXT NOT NULL,
                quantity REAL DEFAULT 1,
                unit_price REAL DEFAULT 0,
                amount REAL DEFAULT 0,
                FOREIGN KEY (quotation_id) REFERENCES quotations (id) ON DELETE CASCADE
            )
        ''')
        
        # Invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                quotation_id INTEGER,
                customer_id INTEGER,
                date TEXT NOT NULL,
                due_date TEXT,
                status TEXT DEFAULT 'Unpaid',
                notes TEXT,
                subtotal REAL DEFAULT 0,
                tax_rate REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                discount REAL DEFAULT 0,
                total REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                FOREIGN KEY (quotation_id) REFERENCES quotations (id),
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Invoice items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                description TEXT NOT NULL,
                quantity REAL DEFAULT 1,
                unit_price REAL DEFAULT 0,
                amount REAL DEFAULT 0,
                FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
            )
        ''')
        
        self.conn.commit()
    
    def execute_query(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

class CompanySettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.setWindowTitle("Company Settings")
        self.setMinimumWidth(500)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        self.company_name = QLineEdit()
        self.address = QTextEdit()
        self.address.setMaximumHeight(80)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.website = QLineEdit()
        
        layout.addRow("Company Name:", self.company_name)
        layout.addRow("Address:", self.address)
        layout.addRow("Phone:", self.phone)
        layout.addRow("Email:", self.email)
        layout.addRow("Website:", self.website)
        
        # Logo
        logo_layout = QHBoxLayout()
        self.logo_path = QLineEdit()
        self.logo_path.setReadOnly(True)
        logo_layout.addWidget(self.logo_path)
        browse_btn = QPushButton("Browse Logo")
        browse_btn.clicked.connect(self.browse_logo)
        logo_layout.addWidget(browse_btn)
        layout.addRow("Logo:", logo_layout)
        
        # SMTP Settings
        smtp_group = QGroupBox("Email (SMTP) Settings")
        smtp_layout = QFormLayout()
        self.smtp_server = QLineEdit()
        self.smtp_port = QLineEdit()
        self.smtp_port.setPlaceholderText("587")
        self.smtp_username = QLineEdit()
        self.smtp_password = QLineEdit()
        self.smtp_password.setEchoMode(QLineEdit.Password)
        smtp_layout.addRow("SMTP Server:", self.smtp_server)
        smtp_layout.addRow("SMTP Port:", self.smtp_port)
        smtp_layout.addRow("Username:", self.smtp_username)
        smtp_layout.addRow("Password:", self.smtp_password)
        smtp_group.setLayout(smtp_layout)
        layout.addRow(smtp_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.logo_path.setText(file_path)
    
    def load_settings(self):
        settings = self.db.fetch_one("SELECT * FROM company_settings WHERE id = 1")
        if settings:
            self.company_name.setText(settings[1] if settings[1] else "")
            self.address.setText(settings[2] if settings[2] else "")
            self.phone.setText(settings[3] if settings[3] else "")
            self.email.setText(settings[4] if settings[4] else "")
            self.website.setText(settings[5] if settings[5] else "")
            self.logo_path.setText(settings[6] if settings[6] else "")
            self.smtp_server.setText(settings[7] if len(settings) > 7 and settings[7] else "")
            self.smtp_port.setText(settings[8] if len(settings) > 8 and settings[8] else "")
            self.smtp_username.setText(settings[9] if len(settings) > 9 and settings[9] else "")
            self.smtp_password.setText(settings[10] if len(settings) > 10 and settings[10] else "")
    
    def save_settings(self):
        self.db.execute_query(
            """UPDATE company_settings 
            SET company_name=?, address=?, phone=?, email=?, website=?, logo_path=?,
                smtp_server=?, smtp_port=?, smtp_username=?, smtp_password=?
            WHERE id=1""",
            (self.company_name.text(), self.address.toPlainText(), 
             self.phone.text(), self.email.text(), self.website.text(), 
             self.logo_path.text(),
             self.smtp_server.text(), self.smtp_port.text(),
             self.smtp_username.text(), self.smtp_password.text())
        )
        self.accept()

class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer_data=None):
        super().__init__(parent)
        self.customer_data = customer_data
        self.setWindowTitle("Add Customer" if not customer_data else "Edit Customer")
        self.setMinimumWidth(400)
        self.setup_ui()
        
        if customer_data:
            self.load_customer_data()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.company_input = QLineEdit()
        self.address_input = QTextEdit()
        self.address_input.setMaximumHeight(80)
        self.email_input = QLineEdit()
        self.phone_input = QLineEdit()
        
        layout.addRow("Name:*", self.name_input)
        layout.addRow("Company:", self.company_input)
        layout.addRow("Address:", self.address_input)
        layout.addRow("Email:", self.email_input)
        layout.addRow("Phone:", self.phone_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def load_customer_data(self):
        self.name_input.setText(self.customer_data.get('name', ''))
        self.company_input.setText(self.customer_data.get('company', ''))
        self.address_input.setText(self.customer_data.get('address', ''))
        self.email_input.setText(self.customer_data.get('email', ''))
        self.phone_input.setText(self.customer_data.get('phone', ''))
    
    def get_customer_data(self):
        return {
            'name': self.name_input.text(),
            'company': self.company_input.text(),
            'address': self.address_input.toPlainText(),
            'email': self.email_input.text(),
            'phone': self.phone_input.text()
        }

class PDFGenerator:
    def __init__(self, db):
        self.db = db
        self.page_width, self.page_height = A4
    
    def get_company_settings(self):
        return self.db.fetch_one("SELECT * FROM company_settings WHERE id = 1")
    
    def wrap_text(self, text, max_chars_per_line=50):
        """Wrap text to fit within column width"""
        if not text:
            return ""
        return textwrap.fill(str(text), width=max_chars_per_line)
    
    def create_table_with_proper_wrapping(self, items, total_data, is_invoice=False):
        """Create a properly formatted table with text wrapping"""
        
        # Available width for the table (with margins)
        available_width = self.page_width - 2 * inch  # 1 inch margins on each side
        
        # Column width distribution (percentage of available width)
        col_widths = [
            available_width * 0.45,  # Description - 45% of width
            available_width * 0.15,  # Quantity - 15%
            available_width * 0.20,  # Unit Price - 20%
            available_width * 0.20,  # Amount - 20%
        ]
        
        # Prepare table data
        table_data = []
        
        # Header
        header = [
            Paragraph('<b>Description</b>', self.get_cell_style('header')),
            Paragraph('<b>Qty</b>', self.get_cell_style('header_center')),
            Paragraph('<b>Unit Price</b>', self.get_cell_style('header_center')),
            Paragraph('<b>Amount</b>', self.get_cell_style('header_center'))
        ]
        table_data.append(header)
        
        # Item rows
        for item in items:
            row = [
                Paragraph(self.wrap_text(item[0], 40), self.get_cell_style('normal')),
                Paragraph(str(item[1]), self.get_cell_style('center')),
                Paragraph(f"RM{item[2]:.2f}", self.get_cell_style('right')),
                Paragraph(f"RM{item[3]:.2f}", self.get_cell_style('right'))
            ]
            table_data.append(row)
        
        # Add empty rows if needed for better appearance
        empty_rows = max(0, 5 - len(items))
        for _ in range(empty_rows):
            table_data.append([
                Paragraph('', self.get_cell_style('normal')),
                Paragraph('', self.get_cell_style('center')),
                Paragraph('', self.get_cell_style('right')),
                Paragraph('', self.get_cell_style('right'))
            ])
        
        # Add total rows
        for label, value in total_data:
            table_data.append([
                Paragraph('', self.get_cell_style('normal')),
                Paragraph('', self.get_cell_style('center')),
                Paragraph(f'<b>{label}</b>', self.get_cell_style('right_bold')),
                Paragraph(f'<b>{value}</b>', self.get_cell_style('right_bold'))
            ])
        
        # Create table
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Style the table
        style_commands = [
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            
            # Grid for data rows only (not total rows)
            ('INNERGRID', (0, 0), (-1, -len(total_data)-1), 0.5, colors.HexColor('#dee2e6')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2c3e50')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#2c3e50')),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -len(total_data)-1), [colors.white, colors.HexColor('#f8f9fa')]),
            
            # Padding for all cells
            ('TOPPADDING', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            
            # Total rows style
            ('LINEABOVE', (0, -len(total_data)), (-1, -len(total_data)), 1, colors.HexColor('#2c3e50')),
            ('BACKGROUND', (0, -len(total_data)), (-1, -1), colors.HexColor('#f0f4f8')),
            
            # Last total row (grand total)
            ('LINEABOVE', (0, -1), (-1, -1), 2.5, colors.HexColor('#2c3e50')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5dfe8')),
            ('FONTSIZE', (0, -1), (-1, -1), 11),
        ]
        
        table.setStyle(TableStyle(style_commands))
        
        return table
    
    def get_cell_style(self, style_type):
        """Get paragraph style for table cells"""
        if style_type == 'header':
            return ParagraphStyle(
                'HeaderCell',
                fontSize=10,
                leading=12,
                alignment=TA_LEFT,
                textColor=colors.white,
                fontName='Helvetica-Bold'
            )
        elif style_type == 'header_center':
            return ParagraphStyle(
                'HeaderCenterCell',
                fontSize=10,
                leading=12,
                alignment=TA_CENTER,
                textColor=colors.white,
                fontName='Helvetica-Bold'
            )
        elif style_type == 'normal':
            return ParagraphStyle(
                'NormalCell',
                fontSize=9,
                leading=11,
                alignment=TA_LEFT,
                fontName='Helvetica'
            )
        elif style_type == 'center':
            return ParagraphStyle(
                'CenterCell',
                fontSize=9,
                leading=11,
                alignment=TA_CENTER,
                fontName='Helvetica'
            )
        elif style_type == 'right':
            return ParagraphStyle(
                'RightCell',
                fontSize=9,
                leading=11,
                alignment=TA_RIGHT,
                fontName='Helvetica'
            )
        elif style_type == 'right_bold':
            return ParagraphStyle(
                'RightBoldCell',
                fontSize=10,
                leading=13,
                alignment=TA_RIGHT,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#2c3e50')
            )
    
    def generate_quotation_pdf(self, quote_number, sig_data=None, draft=True):
        # Get quotation data
        quote = self.db.fetch_one("""
            SELECT q.*, c.name, c.company, c.address, c.email, c.phone
            FROM quotations q
            LEFT JOIN customers c ON q.customer_id = c.id
            WHERE q.quote_number = ?
        """, (quote_number,))
        
        if not quote:
            return None, "Quotation not found"
        
        items = self.db.fetch_all("""
            SELECT description, quantity, unit_price, amount
            FROM quotation_items
            WHERE quotation_id = ?
        """, (quote[0],))
        
        company = self.get_company_settings()
        
        # Create PDF
        filename = f"Quotation_{quote_number}.pdf"
        doc = SimpleDocTemplate(
            filename, 
            pagesize=A4,
            leftMargin=1*inch,
            rightMargin=1*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d')
        )
        
        quotation_title_style = ParagraphStyle(
            'QuotationTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=0,
            alignment=TA_CENTER,
            textColor=colors.white
        )
        
        # Header section with company info and logo
        header_table_data = []
        
        # Company info (left side)
        if company:
            company_name = company[1] or "Your Company Name"
            company_address = company[2] or ""
            company_phone = company[3] or ""
            company_email = company[4] or ""
            
            company_info = f"""
            <font size="16" color="#00FF00"><b>{company_name}</b></font><br/>
            <font size="10">{company_address.replace(chr(10), '<br/>')}</font><br/>
            <font size="10">Phone: {company_phone}<br/>
            Email: {company_email}</font>
            """
        else:
            company_info = "<b>Your Company Name</b><br/>Your Company Details"
        
        company_cell = Paragraph(company_info, styles['Normal'])
        
        # Logo (right side) - if exists
        if company and company[6] and os.path.exists(company[6]):
            try:
                logo = Image(company[6], width=1.5*inch, height=0.75*inch)
                logo_cell = logo
            except:
                logo_cell = Paragraph('', styles['Normal'])
        else:
            logo_cell = Paragraph('', styles['Normal'])
        
        header_table = Table(
            [[company_cell, logo_cell]], 
            colWidths=[self.page_width * 0.6, self.page_width * 0.2]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        
        # Horizontal line
        elements.append(HRFlowable(
            width="100%", 
            thickness=2, 
            color=colors.HexColor('#2c3e50')
        ))
        elements.append(Spacer(1, 15))
        
        # Title banner
        title_label = "QUOTATION (DRAFT)" if draft else "QUOTATION"
        title_bg = Table(
            [[Paragraph(title_label, quotation_title_style)]],
            colWidths=[self.page_width - 2*inch]
        )
        title_bg.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(title_bg)
        elements.append(Spacer(1, 6))
        subtitle_info = f"<b>Quote #:</b> {quote[1]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date:</b> {quote[3]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Valid Until:</b> {quote[4]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Status:</b> {quote[5]}"
        elements.append(Paragraph(subtitle_info, subtitle_style))
        elements.append(Spacer(1, 20))
        
        # Quotation and Customer information side by side
        info_table_data = []
        col_w = (self.page_width - 2*inch) / 2
        
        # Quote details (left)
        quote_details = f"""
        <b>Quote Number:</b><br/>
        {quote[1]}<br/><br/>
        <b>Date:</b><br/>
        {quote[3]}<br/><br/>
        <b>Valid Until:</b><br/>
        {quote[4]}<br/><br/>
        <b>Status:</b><br/>
        {quote[5]}
        """
        quote_cell = Paragraph(quote_details, styles['Normal'])
        quote_box = Table([[quote_cell]], colWidths=[col_w - 6])
        quote_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        # Customer details (right)
        customer_details = f"""
        <b>Bill To:</b><br/>
        {quote[12]}<br/>
        {f'{quote[13]}<br/>' if quote[13] else ''}
        {f'{quote[14].replace(chr(10), "<br/>")}<br/>' if quote[14] else ''}
        {f'<br/><b>Email:</b> {quote[15]}<br/>' if quote[15] else ''}
        {f'<b>Phone:</b> {quote[16]}' if quote[16] else ''}
        """
        customer_cell = Paragraph(customer_details, styles['Normal'])
        customer_box = Table([[customer_cell]], colWidths=[col_w - 6])
        customer_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LINELEFT', (0, 0), (-1, -1), 3, colors.HexColor('#2c3e50')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        info_table = Table(
            [[quote_box, customer_box]], 
            colWidths=[col_w, col_w]
        )
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 25))
        
        # Items table
        subtotal = quote[7]
        discount = quote[10]
        total_data = [('Subtotal:', f"RM{subtotal:.2f}")]
        
        if draft:
            total_data.append((f'Margin ({quote[8]}%):', f"RM{quote[9]:.2f}"))
            final_total = quote[11]
        else:
            final_total = subtotal - discount
        
        if discount > 0:
            total_data.append(('Discount:', f"-RM{discount:.2f}"))
        
        total_data.append(('Total:', f"RM{final_total:.2f}"))
        
        items_table = self.create_table_with_proper_wrapping(items, total_data)
        elements.append(items_table)
        elements.append(Spacer(1, 20))
        
        # Notes
        if quote[6]:
            elements.append(Spacer(1, 10))
            notes_box = Table(
                [[Paragraph(f"<b>Notes:</b><br/>{quote[6].replace(chr(10), '<br/>')}", styles['Normal'])]],
                colWidths=[self.page_width - 2*inch]
            )
            notes_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff3cd')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#ffc107')),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(notes_box)
        
        # Signature
        if sig_data:
            elements.append(Spacer(1, 35))
            sig_style = ParagraphStyle(
                'Signature',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_RIGHT,
                spaceAfter=4
            )
            sig_label = ParagraphStyle(
                'SigLabel',
                parent=styles['Normal'],
                fontSize=9,
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#555555')
            )
            sig_text = f"<b>Authorized Signature</b><br/>"
            elements.append(Paragraph(sig_text, sig_style))
            sig_table = Table(
                [[Paragraph("___________________________", sig_style)]],
                colWidths=[2*inch]
            )
            sig_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ]))
            elements.append(sig_table)
            if sig_data.get('authorized_by'):
                elements.append(Paragraph(sig_data['authorized_by'], sig_style))
            if sig_data.get('designation'):
                elements.append(Paragraph(sig_data['designation'], sig_label))
            if sig_data.get('date'):
                elements.append(Paragraph(sig_data['date'], sig_label))
        
        # Footer
        elements.append(Spacer(1, 40))
        elements.append(HRFlowable(
            width="100%", 
            thickness=1, 
            color=colors.HexColor('#bdc3c7')
        ))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#95a5a6'),
            alignment=TA_CENTER
        )
        footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y %H:%M')}"
        if company and company[1]:
            footer_text += f" | {company[1]}"
        elements.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            return filename, str(e)
        return filename, None
    
    def generate_invoice_pdf(self, invoice_number, sig_data=None):
        # Get invoice data
        invoice = self.db.fetch_one("""
            SELECT i.*, c.name, c.company, c.address, c.email, c.phone
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.invoice_number = ?
        """, (invoice_number,))
        
        if not invoice:
            return None, "Invoice not found"
        
        items = self.db.fetch_all("""
            SELECT description, quantity, unit_price, amount
            FROM invoice_items
            WHERE invoice_id = ?
        """, (invoice[0],))
        
        company = self.get_company_settings()
        
        # Create PDF
        filename = f"Invoice_{invoice_number}.pdf"
        doc = SimpleDocTemplate(
            filename, 
            pagesize=A4,
            leftMargin=1*inch,
            rightMargin=1*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d')
        )
        
        # Header section
        if company:
            company_name = company[1] or "Your Company Name"
            company_address = company[2] or ""
            company_phone = company[3] or ""
            company_email = company[4] or ""
            
            company_info = f"""
            <font size="16" color="#00FF00"><b>{company_name}</b></font><br/>
            <font size="10">{company_address.replace(chr(10), '<br/>')}</font><br/>
            <font size="10">Phone: {company_phone}<br/>
            Email: {company_email}</font>
            """
        else:
            company_info = "<b>Your Company Name</b><br/>Your Company Details"
        
        company_cell = Paragraph(company_info, styles['Normal'])
        
        # Logo
        if company and company[6] and os.path.exists(company[6]):
            try:
                logo = Image(company[6], width=1.5*inch, height=0.75*inch)
                logo_cell = logo
            except:
                logo_cell = Paragraph('', styles['Normal'])
        else:
            logo_cell = Paragraph('', styles['Normal'])
        
        header_table = Table(
            [[company_cell, logo_cell]], 
            colWidths=[self.page_width * 0.6, self.page_width * 0.2]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2c3e50')))
        elements.append(Spacer(1, 15))
        
        # Title with status
        if invoice[6] == "Paid":
            status_text = '<font color="white">● PAID</font>'
        elif invoice[6] == "Overdue":
            status_text = '<font color="white">● OVERDUE</font>'
        else:
            status_text = '<font color="white">● UNPAID</font>'
        
        inv_title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=0,
            alignment=TA_CENTER,
            textColor=colors.white
        )
        title_bg = Table(
            [[Paragraph(f"INVOICE &nbsp;&nbsp; {status_text}", inv_title_style)]],
            colWidths=[self.page_width - 2*inch]
        )
        title_bg.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(title_bg)
        elements.append(Spacer(1, 6))
        subtitle_info = f"<b>Invoice #:</b> {invoice[1]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date:</b> {invoice[4]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Due Date:</b> {invoice[5]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Status:</b> {invoice[6]}"
        elements.append(Paragraph(subtitle_info, subtitle_style))
        elements.append(Spacer(1, 20))
        
        # Invoice and Customer information
        col_w = (self.page_width - 2*inch) / 2
        invoice_details = f"""
        <b>Invoice Number:</b><br/>
        {invoice[1]}<br/><br/>
        <b>Date:</b><br/>
        {invoice[4]}<br/><br/>
        <b>Due Date:</b><br/>
        {invoice[5]}<br/><br/>
        <b>Status:</b><br/>
        {invoice[6]}
        """
        invoice_cell = Paragraph(invoice_details, styles['Normal'])
        invoice_box = Table([[invoice_cell]], colWidths=[col_w - 6])
        invoice_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        customer_details = f"""
        <b>Bill To:</b><br/>
        {invoice[12]}<br/>
        {f'{invoice[13]}<br/>' if invoice[13] else ''}
        {f'{invoice[14].replace(chr(10), "<br/>")}<br/>' if invoice[14] else ''}
        {f'<br/><b>Email:</b> {invoice[15]}<br/>' if invoice[15] else ''}
        {f'<b>Phone:</b> {invoice[16]}' if invoice[16] else ''}
        """
        customer_cell = Paragraph(customer_details, styles['Normal'])
        customer_box = Table([[customer_cell]], colWidths=[col_w - 6])
        customer_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LINELEFT', (0, 0), (-1, -1), 3, colors.HexColor('#2c3e50')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        info_table = Table(
            [[invoice_box, customer_box]], 
            colWidths=[col_w, col_w]
        )
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 25))
        
        # Items table
        balance = invoice[12] - invoice[13]
        total_data = [
            ('Subtotal:', f"RM{invoice[8]:.2f}"),
            (f'Margin ({invoice[9]}%):', f"RM{invoice[10]:.2f}"),
        ]
        
        if invoice[11] > 0:
            total_data.append(('Discount:', f"-RM{invoice[11]:.2f}"))
        
        total_data.append(('Total:', f"RM{invoice[12]:.2f}"))
        total_data.append(('Amount Paid:', f"RM{invoice[13]:.2f}"))
        
        if balance > 0:
            total_data.append(('Balance Due:', f"RM{balance:.2f}"))
        
        items_table = self.create_table_with_proper_wrapping(items, total_data, is_invoice=True)
        elements.append(items_table)
        elements.append(Spacer(1, 20))
        
        # Notes
        if invoice[7]:
            elements.append(Spacer(1, 10))
            notes_box = Table(
                [[Paragraph(f"<b>Notes:</b><br/>{invoice[7].replace(chr(10), '<br/>')}", styles['Normal'])]],
                colWidths=[self.page_width - 2*inch]
            )
            notes_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff3cd')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#ffc107')),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(notes_box)
        
        # Signature
        if sig_data:
            elements.append(Spacer(1, 35))
            sig_style = ParagraphStyle(
                'Signature',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_RIGHT,
                spaceAfter=4
            )
            sig_label = ParagraphStyle(
                'SigLabel',
                parent=styles['Normal'],
                fontSize=9,
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#555555')
            )
            sig_text = f"<b>Authorized Signature</b><br/>"
            elements.append(Paragraph(sig_text, sig_style))
            sig_table = Table(
                [[Paragraph("___________________________", sig_style)]],
                colWidths=[2*inch]
            )
            sig_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ]))
            elements.append(sig_table)
            if sig_data.get('authorized_by'):
                elements.append(Paragraph(sig_data['authorized_by'], sig_style))
            if sig_data.get('designation'):
                elements.append(Paragraph(sig_data['designation'], sig_label))
            if sig_data.get('date'):
                elements.append(Paragraph(sig_data['date'], sig_label))
        
        # Payment status stamp
        if invoice[6] == "Paid":
            elements.append(Spacer(1, 30))
            paid_style = ParagraphStyle(
                'PaidStamp',
                fontSize=36,
                textColor=colors.HexColor('#27ae60'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("PAID IN FULL", paid_style))
        
        # Footer
        elements.append(Spacer(1, 40))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#95a5a6'),
            alignment=TA_CENTER
        )
        footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y %H:%M')}"
        if company and company[1]:
            footer_text += f" | {company[1]}"
        elements.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            return filename, str(e)
        return filename, None

class EmailDialog(QDialog):
    def __init__(self, parent, customer_email="", pdf_path=None, subject="", body=""):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.setWindowTitle("Send Email")
        self.setMinimumWidth(500)
        self.setup_ui(customer_email, subject, body)

    def setup_ui(self, customer_email, subject, body):
        layout = QVBoxLayout()
        form = QFormLayout()
        self.to_input = QLineEdit(customer_email)
        self.subject_input = QLineEdit(subject)
        self.body_input = QTextEdit(body)
        self.body_input.setMinimumHeight(150)
        form.addRow("To:", self.to_input)
        form.addRow("Subject:", self.subject_input)
        form.addRow("Body:", self.body_input)
        layout.addLayout(form)

        if self.pdf_path:
            self.attach_check = QCheckBox(f"Attach PDF: {os.path.basename(self.pdf_path)}")
            self.attach_check.setChecked(True)
            layout.addWidget(self.attach_check)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def get_email_data(self):
        return {
            'to': self.to_input.text(),
            'subject': self.subject_input.text(),
            'body': self.body_input.toPlainText(),
            'attach_pdf': self.pdf_path if hasattr(self, 'attach_check') and self.attach_check.isChecked() else None
        }

    @staticmethod
    def send_email(parent, smtp_settings, to, subject, body, pdf_path=None):
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_settings['username']
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(pdf_path)}"')
                msg.attach(part)

            port = int(smtp_settings['port']) if smtp_settings['port'] else 587
            server = smtplib.SMTP(smtp_settings['server'], port)
            server.starttls()
            server.login(smtp_settings['username'], smtp_settings['password'])
            server.send_message(msg)
            server.quit()
            return None
        except Exception as e:
            return str(e)

class QuotationInvoiceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.pdf_generator = PDFGenerator(self.db)
        self.current_quote_items = []
        self.current_invoice_items = []
        self.editing_quote_id = None
        self.editing_invoice_id = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Quotation & Invoice Management System")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Add tabs
        self.quotation_tab = self.create_draft_tab()
        self.create_quotation_tab = self.create_cq_tab()
        self.invoice_tab = self.create_invoice_tab()
        self.manage_tab = self.create_management_tab()
        self.customer_tab = self.create_customer_tab()
        
        tabs.addTab(self.quotation_tab, "Draft Quotation")
        tabs.addTab(self.create_quotation_tab, "Create Quotation")
        tabs.addTab(self.invoice_tab, "Create Invoice")
        tabs.addTab(self.manage_tab, "Manage Records")
        tabs.addTab(self.customer_tab, "Manage Customers")
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        settings_action = file_menu.addAction('Company Settings')
        settings_action.triggered.connect(self.open_company_settings)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)
    
    def open_company_settings(self):
        dialog = CompanySettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "Success", "Company settings updated!")
    
    def create_draft_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Customer Information
        customer_group = QGroupBox("Customer Information")
        customer_layout = QGridLayout()
        
        customer_layout.addWidget(QLabel("Select Customer:"), 0, 0)
        self.quote_customer_combo = QComboBox()
        self.load_customers(self.quote_customer_combo)
        customer_layout.addWidget(self.quote_customer_combo, 0, 1)
        
        self.quote_add_customer_btn = QPushButton("New Customer")
        self.quote_add_customer_btn.clicked.connect(self.add_customer)
        customer_layout.addWidget(self.quote_add_customer_btn, 0, 2)
        
        customer_layout.addWidget(QLabel("Quote Number:"), 1, 0)
        self.quote_number_input = QLineEdit()
        self.quote_number_input.setText(f"Q-{datetime.now().strftime('%Y%m%d')}-001")
        customer_layout.addWidget(self.quote_number_input, 1, 1)
        
        customer_layout.addWidget(QLabel("Date:"), 2, 0)
        self.quote_date_input = QDateEdit(QDate.currentDate())
        self.quote_date_input.setCalendarPopup(True)
        customer_layout.addWidget(self.quote_date_input, 2, 1)
        
        customer_layout.addWidget(QLabel("Valid Until:"), 2, 2)
        self.quote_valid_until = QDateEdit(QDate.currentDate().addDays(30))
        self.quote_valid_until.setCalendarPopup(True)
        customer_layout.addWidget(self.quote_valid_until, 3, 1)
        
        customer_group.setLayout(customer_layout)
        layout.addWidget(customer_group)
        
        # Quotation Items
        items_group = QGroupBox("Quotation Items")
        items_layout = QVBoxLayout()
        
        self.quote_items_table = QTableWidget()
        self.quote_items_table.setColumnCount(5)
        self.quote_items_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "Amount", "Action"])
        self.quote_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        items_layout.addWidget(self.quote_items_table)
        
        add_item_btn = QPushButton("Add Item")
        add_item_btn.clicked.connect(self.add_quote_item)
        items_layout.addWidget(add_item_btn)
        
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)
        
        # Totals and Notes
        totals_group = QGroupBox("Summary")
        totals_layout = QGridLayout()
        
        totals_layout.addWidget(QLabel("Subtotal:"), 0, 0)
        self.quote_subtotal = QLabel("RM0.00")
        totals_layout.addWidget(self.quote_subtotal, 0, 1)
        
        totals_layout.addWidget(QLabel("Margin (%):"), 1, 0)
        self.quote_margin_rate = QDoubleSpinBox()
        self.quote_margin_rate.setMaximum(1000000)
        self.quote_margin_rate.valueChanged.connect(self.update_quote_totals)
        totals_layout.addWidget(self.quote_margin_rate, 1, 1)
        
        totals_layout.addWidget(QLabel("Margin Amount:"), 2, 0)
        self.quote_margin_amount = QLabel("RM0.00")
        totals_layout.addWidget(self.quote_margin_amount, 2, 1)
        
        totals_layout.addWidget(QLabel("Discount:"), 3, 0)
        self.quote_discount = QDoubleSpinBox()
        self.quote_discount.setMaximum(1000000)
        self.quote_discount.valueChanged.connect(self.update_quote_totals)
        totals_layout.addWidget(self.quote_discount, 3, 1)
        
        totals_layout.addWidget(QLabel("Total:"), 4, 0)
        self.quote_total = QLabel("RM0.00")
        font = QFont()
        font.setBold(True)
        self.quote_total.setFont(font)
        totals_layout.addWidget(self.quote_total, 4, 1)
        
        totals_layout.addWidget(QLabel("Notes:"), 5, 0)
        self.quote_notes = QTextEdit()
        self.quote_notes.setMaximumHeight(80)
        totals_layout.addWidget(self.quote_notes, 5, 1)
        
        totals_group.setLayout(totals_layout)
        layout.addWidget(totals_group)
        
        # Margin Allocation
        margin_group = QGroupBox("Margin Allocation")
        margin_layout = QVBoxLayout()
        self.margin_table = QTableWidget()
        self.margin_table.setColumnCount(2)
        self.margin_table.setHorizontalHeaderLabels(["Category", "Amount (RM)"])
        self.margin_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        margin_layout.addWidget(self.margin_table)
        add_margin_btn = QPushButton("Add Allocation")
        add_margin_btn.clicked.connect(self.add_margin_allocation)
        margin_layout.addWidget(add_margin_btn)
        self.margin_remaining_label = QLabel("Remaining: RM0.00")
        margin_layout.addWidget(self.margin_remaining_label)
        margin_group.setLayout(margin_layout)
        layout.addWidget(margin_group)
        
        # Signature
        sig_group = QGroupBox("Signature")
        sig_layout = QFormLayout()
        self.quote_authorized_by = QLineEdit()
        self.quote_designation = QLineEdit()
        self.quote_sig_date = QDateEdit(QDate.currentDate())
        self.quote_sig_date.setCalendarPopup(True)
        sig_layout.addRow("Authorized By:", self.quote_authorized_by)
        sig_layout.addRow("Designation:", self.quote_designation)
        sig_layout.addRow("Date:", self.quote_sig_date)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        transfer_btn = QPushButton("Transfer to Create Quotation")
        transfer_btn.clicked.connect(self.transfer_to_create_quotation)
        action_layout.addWidget(transfer_btn)
        
        print_btn = QPushButton("Print Draft")
        print_btn.clicked.connect(lambda: self.print_quotation_to_pdf())
        action_layout.addWidget(print_btn)
        
        convert_btn = QPushButton("Convert to Invoice")
        convert_btn.clicked.connect(self.convert_to_invoice)
        action_layout.addWidget(convert_btn)
        
        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self.clear_quote_form)
        action_layout.addWidget(clear_btn)
        
        email_btn = QPushButton("Send Email")
        email_btn.clicked.connect(self.send_email_quotation)
        action_layout.addWidget(email_btn)
        
        layout.addLayout(action_layout)
        
        scroll.setWidget(widget)
        return scroll
    
    def create_cq_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Customer Information
        customer_group = QGroupBox("Customer Information")
        customer_layout = QGridLayout()
        
        customer_layout.addWidget(QLabel("Select Customer:"), 0, 0)
        self.cq_customer_combo = QComboBox()
        self.load_customers(self.cq_customer_combo)
        customer_layout.addWidget(self.cq_customer_combo, 0, 1)
        
        self.cq_add_customer_btn = QPushButton("New Customer")
        self.cq_add_customer_btn.clicked.connect(self.add_customer)
        customer_layout.addWidget(self.cq_add_customer_btn, 0, 2)
        
        customer_layout.addWidget(QLabel("Quote Number:"), 1, 0)
        self.cq_number_input = QLineEdit()
        customer_layout.addWidget(self.cq_number_input, 1, 1)
        
        customer_layout.addWidget(QLabel("Date:"), 2, 0)
        self.cq_date_input = QDateEdit(QDate.currentDate())
        self.cq_date_input.setCalendarPopup(True)
        customer_layout.addWidget(self.cq_date_input, 2, 1)
        
        customer_layout.addWidget(QLabel("Valid Until:"), 2, 2)
        self.cq_valid_until = QDateEdit(QDate.currentDate().addDays(30))
        self.cq_valid_until.setCalendarPopup(True)
        customer_layout.addWidget(self.cq_valid_until, 3, 1)
        
        customer_group.setLayout(customer_layout)
        layout.addWidget(customer_group)
        
        # Items
        items_group = QGroupBox("Quotation Items")
        items_layout = QVBoxLayout()
        
        self.cq_items_table = QTableWidget()
        self.cq_items_table.setColumnCount(5)
        self.cq_items_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "Amount", "Action"])
        self.cq_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        items_layout.addWidget(self.cq_items_table)
        
        add_item_btn = QPushButton("Add Item")
        add_item_btn.clicked.connect(self.add_cq_item)
        items_layout.addWidget(add_item_btn)
        
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)
        
        # Summary
        totals_group = QGroupBox("Summary")
        totals_layout = QGridLayout()
        
        totals_layout.addWidget(QLabel("Subtotal:"), 0, 0)
        self.cq_subtotal = QLabel("RM0.00")
        totals_layout.addWidget(self.cq_subtotal, 0, 1)
        
        totals_layout.addWidget(QLabel("Discount:"), 1, 0)
        self.cq_discount = QDoubleSpinBox()
        self.cq_discount.setMaximum(1000000)
        self.cq_discount.valueChanged.connect(self.update_cq_totals)
        totals_layout.addWidget(self.cq_discount, 1, 1)
        
        totals_layout.addWidget(QLabel("Total:"), 2, 0)
        self.cq_total = QLabel("RM0.00")
        font = QFont()
        font.setBold(True)
        self.cq_total.setFont(font)
        totals_layout.addWidget(self.cq_total, 2, 1)
        
        totals_layout.addWidget(QLabel("Notes:"), 3, 0)
        self.cq_notes = QTextEdit()
        self.cq_notes.setMaximumHeight(80)
        totals_layout.addWidget(self.cq_notes, 3, 1)
        
        totals_group.setLayout(totals_layout)
        layout.addWidget(totals_group)
        
        # Signature
        sig_group = QGroupBox("Signature")
        sig_layout = QFormLayout()
        self.cq_authorized_by = QLineEdit()
        self.cq_designation = QLineEdit()
        self.cq_sig_date = QDateEdit(QDate.currentDate())
        self.cq_sig_date.setCalendarPopup(True)
        sig_layout.addRow("Authorized By:", self.cq_authorized_by)
        sig_layout.addRow("Designation:", self.cq_designation)
        sig_layout.addRow("Date:", self.cq_sig_date)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        create_btn = QPushButton("Create Quotation")
        create_btn.clicked.connect(self.create_cq_quotation)
        action_layout.addWidget(create_btn)
        
        convert_btn = QPushButton("Convert to Invoice")
        convert_btn.clicked.connect(self.convert_cq_to_invoice)
        action_layout.addWidget(convert_btn)
        
        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self.clear_cq_form)
        action_layout.addWidget(clear_btn)
        
        email_btn = QPushButton("Send Email")
        email_btn.clicked.connect(self.send_cq_email)
        action_layout.addWidget(email_btn)
        
        layout.addLayout(action_layout)
        
        scroll.setWidget(widget)
        return scroll
    
    def create_invoice_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Customer Information
        customer_group = QGroupBox("Customer Information")
        customer_layout = QGridLayout()
        
        customer_layout.addWidget(QLabel("Select Customer:"), 0, 0)
        self.invoice_customer_combo = QComboBox()
        self.load_customers(self.invoice_customer_combo)
        customer_layout.addWidget(self.invoice_customer_combo, 0, 1)
        
        self.invoice_add_customer_btn = QPushButton("New Customer")
        self.invoice_add_customer_btn.clicked.connect(self.add_customer)
        customer_layout.addWidget(self.invoice_add_customer_btn, 0, 2)
        
        customer_layout.addWidget(QLabel("Invoice Number:"), 1, 0)
        self.invoice_number_input = QLineEdit()
        self.invoice_number_input.setText(f"INV-{datetime.now().strftime('%Y%m%d')}-001")
        customer_layout.addWidget(self.invoice_number_input, 1, 1)
        
        customer_layout.addWidget(QLabel("Invoice Date:"), 2, 0)
        self.invoice_date_input = QDateEdit(QDate.currentDate())
        self.invoice_date_input.setCalendarPopup(True)
        customer_layout.addWidget(self.invoice_date_input, 2, 1)
        
        customer_layout.addWidget(QLabel("Due Date:"), 2, 2)
        self.invoice_due_date = QDateEdit(QDate.currentDate().addDays(30))
        self.invoice_due_date.setCalendarPopup(True)
        customer_layout.addWidget(self.invoice_due_date, 3, 1)
        
        customer_group.setLayout(customer_layout)
        layout.addWidget(customer_group)
        
        # Invoice Items
        items_group = QGroupBox("Invoice Items")
        items_layout = QVBoxLayout()
        
        self.invoice_items_table = QTableWidget()
        self.invoice_items_table.setColumnCount(5)
        self.invoice_items_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "Amount", "Action"])
        self.invoice_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        items_layout.addWidget(self.invoice_items_table)
        
        add_item_btn = QPushButton("Add Item")
        add_item_btn.clicked.connect(self.add_invoice_item)
        items_layout.addWidget(add_item_btn)
        
        items_group.setLayout(items_layout)
        layout.addWidget(items_group)
        
        # Totals and Notes
        totals_group = QGroupBox("Summary")
        totals_layout = QGridLayout()
        
        totals_layout.addWidget(QLabel("Subtotal:"), 0, 0)
        self.invoice_subtotal = QLabel("RM0.00")
        totals_layout.addWidget(self.invoice_subtotal, 0, 1)
        
        totals_layout.addWidget(QLabel("Tax Rate (%):"), 1, 0)
        self.invoice_tax_rate = QDoubleSpinBox()
        self.invoice_tax_rate.setValue(10)
        self.invoice_tax_rate.valueChanged.connect(self.update_invoice_totals)
        totals_layout.addWidget(self.invoice_tax_rate, 1, 1)
        
        totals_layout.addWidget(QLabel("Tax Amount:"), 2, 0)
        self.invoice_tax_amount = QLabel("RM0.00")
        totals_layout.addWidget(self.invoice_tax_amount, 2, 1)
        
        totals_layout.addWidget(QLabel("Discount:"), 3, 0)
        self.invoice_discount = QDoubleSpinBox()
        self.invoice_discount.setMaximum(1000000)
        self.invoice_discount.valueChanged.connect(self.update_invoice_totals)
        totals_layout.addWidget(self.invoice_discount, 3, 1)
        
        totals_layout.addWidget(QLabel("Total:"), 4, 0)
        self.invoice_total = QLabel("RM0.00")
        font = QFont()
        font.setBold(True)
        self.invoice_total.setFont(font)
        totals_layout.addWidget(self.invoice_total, 4, 1)
        
        totals_layout.addWidget(QLabel("Notes:"), 5, 0)
        self.invoice_notes = QTextEdit()
        self.invoice_notes.setMaximumHeight(80)
        totals_layout.addWidget(self.invoice_notes, 5, 1)
        
        totals_group.setLayout(totals_layout)
        layout.addWidget(totals_group)
        
        # Signature
        sig_group = QGroupBox("Signature")
        sig_layout = QFormLayout()
        self.invoice_authorized_by = QLineEdit()
        self.invoice_designation = QLineEdit()
        self.invoice_sig_date = QDateEdit(QDate.currentDate())
        self.invoice_sig_date.setCalendarPopup(True)
        sig_layout.addRow("Authorized By:", self.invoice_authorized_by)
        sig_layout.addRow("Designation:", self.invoice_designation)
        sig_layout.addRow("Date:", self.invoice_sig_date)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        save_invoice_btn = QPushButton("Save Invoice")
        save_invoice_btn.clicked.connect(self.save_invoice)
        action_layout.addWidget(save_invoice_btn)
        
        print_btn = QPushButton("Print to PDF")
        print_btn.clicked.connect(lambda: self.print_invoice_to_pdf())
        action_layout.addWidget(print_btn)
        
        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self.clear_invoice_form)
        action_layout.addWidget(clear_btn)
        
        email_btn = QPushButton("Send Email")
        email_btn.clicked.connect(self.send_email_invoice)
        action_layout.addWidget(email_btn)
        
        layout.addLayout(action_layout)
        
        return widget
    
    def create_management_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Search and filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by number or customer...")
        self.search_input.textChanged.connect(self.load_records)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addWidget(QLabel("Type:"))
        self.record_type_combo = QComboBox()
        self.record_type_combo.addItems(["All", "Quotations", "Invoices"])
        self.record_type_combo.currentTextChanged.connect(self.load_records)
        filter_layout.addWidget(self.record_type_combo)
        
        layout.addLayout(filter_layout)
        
        # Records table
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(8)
        self.records_table.setHorizontalHeaderLabels([
            "Number", "Type", "Customer", "Date", "Total", "Status", "Paid", "Balance"
        ])
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.records_table.cellDoubleClicked.connect(self.open_record)
        layout.addWidget(self.records_table)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        view_btn = QPushButton("View/Edit")
        view_btn.clicked.connect(self.open_selected_record)
        action_layout.addWidget(view_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_record)
        action_layout.addWidget(delete_btn)
        
        mark_paid_btn = QPushButton("Mark as Paid")
        mark_paid_btn.clicked.connect(self.mark_as_paid)
        action_layout.addWidget(mark_paid_btn)
        
        export_btn = QPushButton("Export to PDF")
        export_btn.clicked.connect(self.export_selected_to_pdf)
        action_layout.addWidget(export_btn)
        
        layout.addLayout(action_layout)
        
        # Load records
        self.load_records()
        
        return widget
    
    # ... (keep all the existing methods from the previous code)
    # [All the methods like load_customers, add_customer, add_quote_item, etc.]
    
    def load_customers(self, combo):
        combo.clear()
        combo.addItem("Select Customer...", None)
        customers = self.db.fetch_all("SELECT id, name, company FROM customers ORDER BY name")
        for customer in customers:
            display = f"{customer[1]}"
            if customer[2]:
                display += f" ({customer[2]})"
            combo.addItem(display, customer[0])
    
    def add_customer(self):
        dialog = CustomerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_customer_data()
            if data['name']:
                self.db.execute_query(
                    "INSERT INTO customers (name, company, address, email, phone) VALUES (?, ?, ?, ?, ?)",
                    (data['name'], data['company'], data['address'], data['email'], data['phone'])
                )
                self.load_customers(self.quote_customer_combo)
                self.load_customers(self.cq_customer_combo)
                self.load_customers(self.invoice_customer_combo)
                QMessageBox.information(self, "Success", "Customer added successfully!")
    
    def create_customer_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.customer_table = QTableWidget()
        self.customer_table.setColumnCount(6)
        self.customer_table.setHorizontalHeaderLabels(["ID", "Name", "Company", "Address", "Email", "Phone"])
        self.customer_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.customer_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.customer_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.customer_table)

        action_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Customer")
        edit_btn.clicked.connect(self.edit_customer)
        action_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Delete Customer")
        delete_btn.clicked.connect(self.delete_customer)
        action_layout.addWidget(delete_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_customer_table)
        action_layout.addWidget(refresh_btn)
        layout.addLayout(action_layout)

        self.load_customer_table()
        return widget

    def load_customer_table(self):
        self.customer_table.setRowCount(0)
        customers = self.db.fetch_all("SELECT id, name, company, address, email, phone FROM customers ORDER BY name")
        for row, customer in enumerate(customers):
            self.customer_table.insertRow(row)
            for col, value in enumerate(customer):
                self.customer_table.setItem(row, col, QTableWidgetItem(str(value) if value else ""))
        self.customer_table.setColumnHidden(0, True)

    def edit_customer(self):
        selected = self.customer_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a customer to edit.")
            return
        row = selected[0].row()
        customer_id = self.customer_table.item(row, 0).text()
        customer = self.db.fetch_one("SELECT id, name, company, address, email, phone FROM customers WHERE id = ?", (customer_id,))
        if not customer:
            QMessageBox.warning(self, "Error", "Customer not found.")
            return
        customer_data = {
            'name': customer[1],
            'company': customer[2],
            'address': customer[3],
            'email': customer[4],
            'phone': customer[5]
        }
        dialog = CustomerDialog(self, customer_data)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_customer_data()
            if data['name']:
                self.db.execute_query(
                    "UPDATE customers SET name=?, company=?, address=?, email=?, phone=? WHERE id=?",
                    (data['name'], data['company'], data['address'], data['email'], data['phone'], customer_id)
                )
                self.load_customer_table()
                self.load_customers(self.quote_customer_combo)
                self.load_customers(self.cq_customer_combo)
                self.load_customers(self.invoice_customer_combo)
                QMessageBox.information(self, "Success", "Customer updated successfully!")

    def delete_customer(self):
        selected = self.customer_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a customer to delete.")
            return
        row = selected[0].row()
        customer_id = self.customer_table.item(row, 0).text()
        customer_name = self.customer_table.item(row, 1).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Are you sure you want to delete '{customer_name}'?\n\nAll quotations and invoices for this customer will also be deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM quotation_items WHERE quotation_id IN (SELECT id FROM quotations WHERE customer_id = ?)", (customer_id,))
                self.db.execute_query("DELETE FROM quotations WHERE customer_id = ?", (customer_id,))
                self.db.execute_query("DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id = ?)", (customer_id,))
                self.db.execute_query("DELETE FROM invoices WHERE customer_id = ?", (customer_id,))
                self.db.execute_query("DELETE FROM customers WHERE id = ?", (customer_id,))
                self.load_customer_table()
                self.load_customers(self.quote_customer_combo)
                self.load_customers(self.cq_customer_combo)
                self.load_customers(self.invoice_customer_combo)
                QMessageBox.information(self, "Success", "Customer deleted successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete customer: {str(e)}")

    def transfer_to_create_quotation(self):
        customer_id = self.quote_customer_combo.currentData()
        self.cq_customer_combo.setCurrentIndex(self.cq_customer_combo.findData(customer_id))
        self.cq_number_input.setText(self.quote_number_input.text())
        self.cq_date_input.setDate(self.quote_date_input.date())
        self.cq_valid_until.setDate(self.quote_valid_until.date())
        
        self.cq_items_table.setRowCount(0)
        for row in range(self.quote_items_table.rowCount()):
            r = self.cq_items_table.rowCount()
            self.cq_items_table.insertRow(r)
            desc_item = QTableWidgetItem(self.quote_items_table.item(row, 0).text() if self.quote_items_table.item(row, 0) else "")
            self.cq_items_table.setItem(r, 0, desc_item)
            qty_w = self.quote_items_table.cellWidget(row, 1)
            qty_spin = QDoubleSpinBox()
            qty_spin.setValue(qty_w.value() if qty_w else 1)
            qty_spin.setMaximum(1000000)
            qty_spin.valueChanged.connect(lambda checked=False, rr=r: self.calculate_cq_item_amount(rr))
            self.cq_items_table.setCellWidget(r, 1, qty_spin)
            price_w = self.quote_items_table.cellWidget(row, 2)
            price_spin = QDoubleSpinBox()
            price_spin.setMaximum(10000000)
            price_spin.setValue(price_w.value() if price_w else 0)
            price_spin.valueChanged.connect(lambda checked=False, rr=r: self.calculate_cq_item_amount(rr))
            self.cq_items_table.setCellWidget(r, 2, price_spin)
            amt_text = self.quote_items_table.item(row, 3).text() if self.quote_items_table.item(row, 3) else "RM0.00"
            self.cq_items_table.setItem(r, 3, QTableWidgetItem(amt_text))
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda checked=False, rr=r: self.delete_cq_item(rr))
            self.cq_items_table.setCellWidget(r, 4, del_btn)
        
        self.cq_discount.setValue(self.quote_discount.value())
        self.cq_notes.setPlainText(self.quote_notes.toPlainText())
        self.cq_authorized_by.setText(self.quote_authorized_by.text())
        self.cq_designation.setText(self.quote_designation.text())
        self.cq_sig_date.setDate(self.quote_sig_date.date())
        self.update_cq_totals()
        QMessageBox.information(self, "Transferred", "Data transferred to Create Quotation tab!")

    def add_cq_item(self):
        row = self.cq_items_table.rowCount()
        self.cq_items_table.insertRow(row)
        
        desc_item = QTableWidgetItem("")
        self.cq_items_table.setItem(row, 0, desc_item)
        
        qty_spin = QDoubleSpinBox()
        qty_spin.setValue(1)
        qty_spin.setMaximum(1000000)
        qty_spin.valueChanged.connect(lambda checked=False, r=row: self.calculate_cq_item_amount(r))
        self.cq_items_table.setCellWidget(row, 1, qty_spin)
        
        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(10000000)
        price_spin.valueChanged.connect(lambda checked=False, r=row: self.calculate_cq_item_amount(r))
        self.cq_items_table.setCellWidget(row, 2, price_spin)
        
        amount_item = QTableWidgetItem("RM0.00")
        self.cq_items_table.setItem(row, 3, amount_item)
        
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(lambda checked=False, r=row: self.delete_cq_item(r))
        self.cq_items_table.setCellWidget(row, 4, del_btn)

    def delete_cq_item(self, row):
        self.cq_items_table.removeRow(row)
        self.update_cq_totals()

    def calculate_cq_item_amount(self, row):
        qty_w = self.cq_items_table.cellWidget(row, 1)
        price_w = self.cq_items_table.cellWidget(row, 2)
        qty = qty_w.value() if qty_w else 0
        price = price_w.value() if price_w else 0
        amount = qty * price
        item = self.cq_items_table.item(row, 3)
        if item:
            item.setText(f"RM{amount:.2f}")
        self.update_cq_totals()

    def update_cq_totals(self):
        subtotal = 0
        for row in range(self.cq_items_table.rowCount()):
            amount_text = self.cq_items_table.item(row, 3).text().replace('RM', '')
            if amount_text:
                subtotal += float(amount_text)
        discount = self.cq_discount.value()
        total = subtotal - discount
        self.cq_subtotal.setText(f"RM{subtotal:.2f}")
        self.cq_total.setText(f"RM{total:.2f}")

    def clear_cq_form(self):
        self.cq_customer_combo.setCurrentIndex(0)
        self.cq_number_input.clear()
        self.cq_date_input.setDate(QDate.currentDate())
        self.cq_valid_until.setDate(QDate.currentDate().addDays(30))
        self.cq_items_table.setRowCount(0)
        self.cq_discount.setValue(0)
        self.cq_notes.clear()
        self.cq_authorized_by.clear()
        self.cq_designation.clear()
        self.cq_sig_date.setDate(QDate.currentDate())
        self.update_cq_totals()

    def create_cq_quotation(self):
        customer_id = self.cq_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        if self.cq_items_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "Please add at least one item!")
            return
        quote_number = self.cq_number_input.text()
        if not quote_number:
            QMessageBox.warning(self, "Warning", "Please enter a quotation number!")
            return
        self.save_cq_quotation()
        quote_number = self.cq_number_input.text()
        progress = QProgressDialog("Generating Quotation PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        try:
            filename, error = self.pdf_generator.generate_quotation_pdf(quote_number, draft=False)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
            return
        progress.close()
        if error:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {error}")
            return
        try:
            if sys.platform == 'win32':
                os.startfile(filename)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filename])
            else:
                subprocess.run(['xdg-open', filename])
        except Exception as e:
            QMessageBox.information(self, "PDF Generated", f"PDF saved as: {filename}\n\nError opening: {str(e)}")
        self.clear_cq_form()

    def save_cq_quotation(self):
        customer_id = self.cq_customer_combo.currentData()
        quote_number = self.cq_number_input.text()
        date_val = self.cq_date_input.date().toString("yyyy-MM-dd")
        valid_until = self.cq_valid_until.date().toString("yyyy-MM-dd")
        
        subtotal = 0
        for row in range(self.cq_items_table.rowCount()):
            amount_text = self.cq_items_table.item(row, 3).text().replace('RM', '')
            if amount_text:
                subtotal += float(amount_text)
        
        discount = self.cq_discount.value()
        total = subtotal - discount
        
        existing = self.db.fetch_one("SELECT id FROM quotations WHERE quote_number = ?", (quote_number,))
        if existing:
            self.db.execute_query(
                "UPDATE quotations SET customer_id=?, date=?, valid_until=?, subtotal=?, discount=?, total=? WHERE id=?",
                (customer_id, date_val, valid_until, subtotal, discount, total, existing[0])
            )
            self.db.execute_query("DELETE FROM quotation_items WHERE quotation_id = ?", (existing[0],))
            quotation_id = existing[0]
        else:
            self.db.execute_query(
                "INSERT INTO quotations (customer_id, quote_number, date, valid_until, subtotal, discount, total) VALUES (?,?,?,?,?,?,?)",
                (customer_id, quote_number, date_val, valid_until, subtotal, discount, total)
            )
            quotation_id = self.db.cursor.lastrowid
        
        for row in range(self.cq_items_table.rowCount()):
            desc = self.cq_items_table.item(row, 0).text() if self.cq_items_table.item(row, 0) else ""
            qty_w = self.cq_items_table.cellWidget(row, 1)
            price_w = self.cq_items_table.cellWidget(row, 2)
            qty = qty_w.value() if qty_w else 0
            price = price_w.value() if price_w else 0
            amount = qty * price
            self.db.execute_query(
                "INSERT INTO quotation_items (quotation_id, description, quantity, unit_price, amount) VALUES (?,?,?,?,?)",
                (quotation_id, desc, qty, price, amount)
            )
            self.cq_items_table.item(row, 3).setText(f"RM{amount:.2f}")
        QMessageBox.information(self, "Success", "Quotation saved successfully!")

    def convert_cq_to_invoice(self):
        customer_id = self.cq_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        if self.cq_items_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "Please add at least one item!")
            return
        
        inv_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{self.cq_number_input.text().split('-')[-1] if '-' in self.cq_number_input.text() else '001'}"
        
        subtotal = 0
        for row in range(self.cq_items_table.rowCount()):
            amount_text = self.cq_items_table.item(row, 3).text().replace('RM', '')
            if amount_text:
                subtotal += float(amount_text)
        
        discount = self.cq_discount.value()
        total = subtotal - discount
        
        date_val = QDate.currentDate().toString("yyyy-MM-dd")
        due_date = QDate.currentDate().addDays(30).toString("yyyy-MM-dd")
        
        self.db.execute_query(
            "INSERT INTO invoices (customer_id, invoice_number, date, due_date, subtotal, discount, total) VALUES (?,?,?,?,?,?,?)",
            (customer_id, inv_number, date_val, due_date, subtotal, discount, total)
        )
        invoice_id = self.db.cursor.lastrowid
        
        for row in range(self.cq_items_table.rowCount()):
            desc = self.cq_items_table.item(row, 0).text() if self.cq_items_table.item(row, 0) else ""
            qty_w = self.cq_items_table.cellWidget(row, 1)
            price_w = self.cq_items_table.cellWidget(row, 2)
            qty = qty_w.value() if qty_w else 0
            price = price_w.value() if price_w else 0
            amount = qty * price
            self.db.execute_query(
                "INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, amount) VALUES (?,?,?,?,?)",
                (invoice_id, desc, qty, price, amount)
            )
        
        self.load_invoices()
        self.load_cq_customers()
        QMessageBox.information(self, "Success", f"Invoice {inv_number} created successfully!")

    def send_cq_email(self):
        customer_id = self.cq_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        customer = self.db.fetch_one("SELECT name, email FROM customers WHERE id = ?", (customer_id,))
        if not customer or not customer[1]:
            QMessageBox.warning(self, "Warning", "Customer has no email address!")
            return
        
        smtp = self.db.fetch_one("SELECT smtp_server, smtp_port, smtp_use_tls, smtp_user, smtp_pass FROM company_settings LIMIT 1")
        if not smtp or not smtp[0]:
            QMessageBox.warning(self, "No SMTP", "Please configure SMTP in Company Settings first!")
            return
        
        quote_number = self.cq_number_input.text()
        subject = f"Quotation {quote_number}"
        body = f"Dear {customer[0]},\n\nPlease find attached the quotation {quote_number}.\n\nThank you."
        dialog = EmailDialog(self, customer[1], None, subject, body)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_email_data()
            self.save_cq_quotation()
            pdf_path = None
            if data['attach_pdf']:
                result = self.pdf_generator.generate_quotation_pdf(quote_number, draft=False)
                if not result[1]:
                    pdf_path = result[0]
            err = EmailDialog.send_email(self, smtp, data['to'], data['subject'], data['body'], pdf_path)
            if err:
                QMessageBox.critical(self, "Error", f"Failed to send email: {err}")
            else:
                QMessageBox.information(self, "Success", "Email sent successfully!")

    def load_cq_customers(self):
        self.load_customers(self.cq_customer_combo)

    def add_quote_item(self):
        row = self.quote_items_table.rowCount()
        self.quote_items_table.insertRow(row)
        
        desc_item = QTableWidgetItem("")
        self.quote_items_table.setItem(row, 0, desc_item)
        
        qty_spin = QDoubleSpinBox()
        qty_spin.setValue(1)
        qty_spin.setMaximum(1000000)
        qty_spin.valueChanged.connect(lambda: self.calculate_quote_item_amount(row))
        self.quote_items_table.setCellWidget(row, 1, qty_spin)
        
        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(1000000)
        price_spin.setValue(0)
        price_spin.valueChanged.connect(lambda: self.calculate_quote_item_amount(row))
        self.quote_items_table.setCellWidget(row, 2, price_spin)
        
        amount_item = QTableWidgetItem("RM0.00")
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
        self.quote_items_table.setItem(row, 3, amount_item)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_quote_item(row))
        self.quote_items_table.setCellWidget(row, 4, delete_btn)
    
    def delete_quote_item(self, row):
        self.quote_items_table.removeRow(row)
        self.update_quote_totals()
    
    def calculate_quote_item_amount(self, row):
        qty_widget = self.quote_items_table.cellWidget(row, 1)
        price_widget = self.quote_items_table.cellWidget(row, 2)
        
        if qty_widget and price_widget:
            amount = qty_widget.value() * price_widget.value()
            self.quote_items_table.item(row, 3).setText(f"RM{amount:.2f}")
        self.update_quote_totals()
    
    def update_quote_totals(self):
        subtotal = 0
        for row in range(self.quote_items_table.rowCount()):
            amount_text = self.quote_items_table.item(row, 3).text().replace('RM', '')
            if amount_text:
                subtotal += float(amount_text)
        
        margin_rate = self.quote_margin_rate.value()
        discount = self.quote_discount.value()
        margin_amount = subtotal * (margin_rate / 100)
        total = subtotal + margin_amount - discount
        
        self.quote_subtotal.setText(f"RM{subtotal:.2f}")
        self.quote_margin_amount.setText(f"RM{margin_amount:.2f}")
        self.quote_total.setText(f"RM{total:.2f}")
        self.update_margin_remaining()
    
    def add_margin_allocation(self):
        row = self.margin_table.rowCount()
        self.margin_table.insertRow(row)
        self.margin_table.setItem(row, 0, QTableWidgetItem(""))
        amt_spin = QDoubleSpinBox()
        amt_spin.setMaximum(10000000)
        amt_spin.valueChanged.connect(self.update_margin_remaining)
        self.margin_table.setCellWidget(row, 1, amt_spin)
    
    def update_margin_remaining(self):
        allocated = 0
        for row in range(self.margin_table.rowCount()):
            widget = self.margin_table.cellWidget(row, 1)
            if widget:
                allocated += widget.value()
        total_margin = 0
        text = self.quote_margin_amount.text().replace('RM', '')
        try:
            total_margin = float(text)
        except:
            pass
        remaining = total_margin - allocated
        if hasattr(self, 'margin_remaining_label'):
            self.margin_remaining_label.setText(f"Remaining: RM{remaining:.2f}")
    
    def add_invoice_item(self):
        row = self.invoice_items_table.rowCount()
        self.invoice_items_table.insertRow(row)
        
        desc_item = QTableWidgetItem("")
        self.invoice_items_table.setItem(row, 0, desc_item)
        
        qty_spin = QDoubleSpinBox()
        qty_spin.setValue(1)
        qty_spin.setMaximum(1000000)
        qty_spin.valueChanged.connect(lambda: self.calculate_invoice_item_amount(row))
        self.invoice_items_table.setCellWidget(row, 1, qty_spin)
        
        price_spin = QDoubleSpinBox()
        price_spin.setMaximum(1000000)
        price_spin.setValue(0)
        price_spin.valueChanged.connect(lambda: self.calculate_invoice_item_amount(row))
        self.invoice_items_table.setCellWidget(row, 2, price_spin)
        
        amount_item = QTableWidgetItem("RM0.00")
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
        self.invoice_items_table.setItem(row, 3, amount_item)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_invoice_item(row))
        self.invoice_items_table.setCellWidget(row, 4, delete_btn)
    
    def delete_invoice_item(self, row):
        self.invoice_items_table.removeRow(row)
        self.update_invoice_totals()
    
    def calculate_invoice_item_amount(self, row):
        qty_widget = self.invoice_items_table.cellWidget(row, 1)
        price_widget = self.invoice_items_table.cellWidget(row, 2)
        
        if qty_widget and price_widget:
            amount = qty_widget.value() * price_widget.value()
            self.invoice_items_table.item(row, 3).setText(f"RM{amount:.2f}")
        self.update_invoice_totals()
    
    def update_invoice_totals(self):
        subtotal = 0
        for row in range(self.invoice_items_table.rowCount()):
            amount_text = self.invoice_items_table.item(row, 3).text().replace('RM', '')
            if amount_text:
                subtotal += float(amount_text)
        
        tax_rate = self.invoice_tax_rate.value()
        discount = self.invoice_discount.value()
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount - discount
        
        self.invoice_subtotal.setText(f"RM{subtotal:.2f}")
        self.invoice_tax_amount.setText(f"RM{tax_amount:.2f}")
        self.invoice_total.setText(f"RM{total:.2f}")
    
    def save_quotation(self, silent=False):
        customer_id = self.quote_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        
        if self.quote_items_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "Please add at least one item!")
            return
        
        quote_number = self.quote_number_input.text()
        
        if not self.editing_quote_id:
            existing = self.db.fetch_one("SELECT id FROM quotations WHERE quote_number = ?", (quote_number,))
            if existing:
                QMessageBox.warning(self, "Warning", "Quotation number already exists!")
                return
        
        date = self.quote_date_input.date().toString("yyyy-MM-dd")
        valid_until = self.quote_valid_until.date().toString("yyyy-MM-dd")
        notes = self.quote_notes.toPlainText()
        subtotal = float(self.quote_subtotal.text().replace('RM', ''))
        margin_rate = self.quote_margin_rate.value()
        margin_amount = float(self.quote_margin_amount.text().replace('RM', ''))
        discount = self.quote_discount.value()
        total = float(self.quote_total.text().replace('RM', ''))
        
        if self.editing_quote_id:
            self.db.execute_query(
                """UPDATE quotations SET customer_id=?, date=?, valid_until=?, notes=?, subtotal=?, tax_rate=?, tax_amount=?, discount=?, total=? WHERE id=?""",
                (customer_id, date, valid_until, notes, subtotal, margin_rate, margin_amount, discount, total, self.editing_quote_id)
            )
            self.db.execute_query("DELETE FROM quotation_items WHERE quotation_id = ?", (self.editing_quote_id,))
            quotation_id = self.editing_quote_id
        else:
            cursor = self.db.execute_query(
                """INSERT INTO quotations 
                (quote_number, customer_id, date, valid_until, notes, subtotal, tax_rate, tax_amount, discount, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (quote_number, customer_id, date, valid_until, notes, subtotal, margin_rate, margin_amount, discount, total)
            )
            quotation_id = cursor.lastrowid
        
        for row in range(self.quote_items_table.rowCount()):
            description = self.quote_items_table.item(row, 0).text()
            qty = self.quote_items_table.cellWidget(row, 1).value()
            price = self.quote_items_table.cellWidget(row, 2).value()
            amount = float(self.quote_items_table.item(row, 3).text().replace('RM', ''))
            
            self.db.execute_query(
                "INSERT INTO quotation_items (quotation_id, description, quantity, unit_price, amount) VALUES (?, ?, ?, ?, ?)",
                (quotation_id, description, qty, price, amount)
            )
        
        if not silent:
            if self.editing_quote_id:
                QMessageBox.information(self, "Success", "Quotation updated successfully!")
            else:
                QMessageBox.information(self, "Success", "Quotation saved successfully!")
            
            reply = QMessageBox.question(self, "Print PDF", 
                                        "Do you want to print this quotation to PDF?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.print_quotation_to_pdf(quote_number)
        
        self.clear_quote_form()
        self.load_records()
    
    def create_quotation(self):
        customer_id = self.quote_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        if self.quote_items_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "Please add at least one item!")
            return
        quote_number = self.quote_number_input.text()
        existing = self.db.fetch_one("SELECT id FROM quotations WHERE quote_number = ?", (quote_number,))
        if not existing:
            self.save_quotation(silent=True)
        quote_number = self.quote_number_input.text()
        progress = QProgressDialog("Generating Quotation PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        try:
            filename, error = self.pdf_generator.generate_quotation_pdf(quote_number, draft=False)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
            return
        progress.close()
        if error:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {error}")
            return
        try:
            if sys.platform == 'win32':
                os.startfile(filename)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filename])
            else:
                subprocess.run(['xdg-open', filename])
        except Exception as e:
            QMessageBox.information(self, "PDF Generated", f"PDF saved as: {filename}\n\nError opening: {str(e)}")
        self.clear_quote_form()
        self.load_records()
    
    def print_quotation_to_pdf(self, quote_number=None):
        from_form = not quote_number
        if not quote_number:
            quote_number = self.quote_number_input.text()
            # Check if quotation exists, if not save it first
            existing = self.db.fetch_one("SELECT id FROM quotations WHERE quote_number = ?", (quote_number,))
            if not existing:
                reply = QMessageBox.question(self, "Save First", 
                                            "Quotation not saved. Save now?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.save_quotation()
                    return
                else:
                    return
        
        progress = QProgressDialog("Generating PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        sig_data = None
        if from_form:
            sig_data = {
                'authorized_by': self.quote_authorized_by.text(),
                'designation': self.quote_designation.text(),
                'date': self.quote_sig_date.date().toString("yyyy-MM-dd")
            }
        try:
            filename, error = self.pdf_generator.generate_quotation_pdf(quote_number, sig_data, draft=True)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
            return
        
        progress.close()
        
        if error:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {error}")
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(filename)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filename])
            else:
                subprocess.run(['xdg-open', filename])
            QMessageBox.information(self, "Success", f"PDF generated: {filename}")
        except Exception as e:
            QMessageBox.information(self, "PDF Generated", 
                                   f"PDF saved as: {filename}\n\nError opening: {str(e)}")
    
    def save_invoice(self):
        customer_id = self.invoice_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        
        if self.invoice_items_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "Please add at least one item!")
            return
        
        invoice_number = self.invoice_number_input.text()
        
        if not self.editing_invoice_id:
            existing = self.db.fetch_one("SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,))
            if existing:
                QMessageBox.warning(self, "Warning", "Invoice number already exists!")
                return
        
        date = self.invoice_date_input.date().toString("yyyy-MM-dd")
        due_date = self.invoice_due_date.date().toString("yyyy-MM-dd")
        notes = self.invoice_notes.toPlainText()
        subtotal = float(self.invoice_subtotal.text().replace('RM', ''))
        tax_rate = self.invoice_tax_rate.value()
        tax_amount = float(self.invoice_tax_amount.text().replace('RM', ''))
        discount = self.invoice_discount.value()
        total = float(self.invoice_total.text().replace('RM', ''))
        
        if self.editing_invoice_id:
            self.db.execute_query(
                """UPDATE invoices SET customer_id=?, date=?, due_date=?, notes=?, subtotal=?, tax_rate=?, tax_amount=?, discount=?, total=? WHERE id=?""",
                (customer_id, date, due_date, notes, subtotal, tax_rate, tax_amount, discount, total, self.editing_invoice_id)
            )
            self.db.execute_query("DELETE FROM invoice_items WHERE invoice_id = ?", (self.editing_invoice_id,))
            invoice_id = self.editing_invoice_id
        else:
            cursor = self.db.execute_query(
                """INSERT INTO invoices 
                (invoice_number, customer_id, date, due_date, notes, subtotal, tax_rate, tax_amount, discount, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_number, customer_id, date, due_date, notes, subtotal, tax_rate, tax_amount, discount, total)
            )
            invoice_id = cursor.lastrowid
        
        for row in range(self.invoice_items_table.rowCount()):
            description = self.invoice_items_table.item(row, 0).text()
            qty = self.invoice_items_table.cellWidget(row, 1).value()
            price = self.invoice_items_table.cellWidget(row, 2).value()
            amount = float(self.invoice_items_table.item(row, 3).text().replace('RM', ''))
            
            self.db.execute_query(
                "INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, amount) VALUES (?, ?, ?, ?, ?)",
                (invoice_id, description, qty, price, amount)
            )
        
        if self.editing_invoice_id:
            QMessageBox.information(self, "Success", "Invoice updated successfully!")
        else:
            QMessageBox.information(self, "Success", "Invoice saved successfully!")
        
        reply = QMessageBox.question(self, "Print PDF", 
                                    "Do you want to print this invoice to PDF?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.print_invoice_to_pdf(invoice_number)
        
        self.clear_invoice_form()
        self.load_records()
    
    def print_invoice_to_pdf(self, invoice_number=None):
        from_form = not invoice_number
        if not invoice_number:
            invoice_number = self.invoice_number_input.text()
            existing = self.db.fetch_one("SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,))
            if not existing:
                reply = QMessageBox.question(self, "Save First", 
                                            "Invoice not saved. Save now?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.save_invoice()
                    return
                else:
                    return
        
        progress = QProgressDialog("Generating PDF...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        sig_data = None
        if from_form:
            sig_data = {
                'authorized_by': self.invoice_authorized_by.text(),
                'designation': self.invoice_designation.text(),
                'date': self.invoice_sig_date.date().toString("yyyy-MM-dd")
            }
        try:
            filename, error = self.pdf_generator.generate_invoice_pdf(invoice_number, sig_data)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
            return

        progress.close()

        if error:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {error}")
            return

        try:
            if sys.platform == 'win32':
                os.startfile(filename)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filename])
            else:
                subprocess.run(['xdg-open', filename])
            QMessageBox.information(self, "Success", f"PDF generated: {filename}")
        except Exception as e:
            QMessageBox.information(self, "PDF Generated", 
                                   f"PDF saved as: {filename}\n\nError opening: {str(e)}")
    
    def convert_to_invoice(self):
        self.save_quotation()
        
        self.clear_invoice_form()
        self.invoice_customer_combo.setCurrentIndex(self.quote_customer_combo.currentIndex())
        self.invoice_notes.setText(self.quote_notes.toPlainText())
        self.invoice_tax_rate.setValue(self.quote_margin_rate.value())
        self.invoice_discount.setValue(self.quote_discount.value())
        self.invoice_authorized_by.setText(self.quote_authorized_by.text())
        self.invoice_designation.setText(self.quote_designation.text())
        self.invoice_sig_date.setDate(self.quote_sig_date.date())
        
        for row in range(self.quote_items_table.rowCount()):
            self.add_invoice_item()
            new_row = self.invoice_items_table.rowCount() - 1
            
            self.invoice_items_table.item(new_row, 0).setText(
                self.quote_items_table.item(row, 0).text()
            )
            self.invoice_items_table.cellWidget(new_row, 1).setValue(
                self.quote_items_table.cellWidget(row, 1).value()
            )
            self.invoice_items_table.cellWidget(new_row, 2).setValue(
                self.quote_items_table.cellWidget(row, 2).value()
            )
        
        self.update_invoice_totals()
        self.centralWidget().findChild(QTabWidget).setCurrentIndex(1)
    
    def send_email_quotation(self):
        customer_id = self.quote_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        customer = self.db.fetch_one("SELECT name, email FROM customers WHERE id = ?", (customer_id,))
        if not customer or not customer[1]:
            QMessageBox.warning(self, "Warning", "Customer has no email address!")
            return
        settings = self.db.fetch_one("SELECT * FROM company_settings WHERE id = 1")
        if not settings or not settings[7] or not settings[9]:
            QMessageBox.warning(self, "Warning", "SMTP not configured! Go to File > Company Settings to set up email.")
            return
        smtp = {'server': settings[7], 'port': settings[8] or '587', 'username': settings[9], 'password': settings[10] or ''}
        quote_number = self.quote_number_input.text()
        subject = f"Quotation {quote_number}"
        body = f"Dear {customer[0]},\n\nPlease find attached the quotation {quote_number}.\n\nThank you."
        dialog = EmailDialog(self, customer[1], None, subject, body)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_email_data()
            self.save_quotation()
            pdf_path = None
            if data['attach_pdf']:
                result = self.pdf_generator.generate_quotation_pdf(quote_number, draft=False)
                if not result[1]:
                    pdf_path = result[0]
            err = EmailDialog.send_email(self, smtp, data['to'], data['subject'], data['body'], pdf_path)
            if err:
                QMessageBox.critical(self, "Error", f"Failed to send email: {err}")
            else:
                QMessageBox.information(self, "Success", "Email sent successfully!")

    def send_email_invoice(self):
        customer_id = self.invoice_customer_combo.currentData()
        if not customer_id:
            QMessageBox.warning(self, "Warning", "Please select a customer!")
            return
        customer = self.db.fetch_one("SELECT name, email FROM customers WHERE id = ?", (customer_id,))
        if not customer or not customer[1]:
            QMessageBox.warning(self, "Warning", "Customer has no email address!")
            return
        settings = self.db.fetch_one("SELECT * FROM company_settings WHERE id = 1")
        if not settings or not settings[7] or not settings[9]:
            QMessageBox.warning(self, "Warning", "SMTP not configured! Go to File > Company Settings to set up email.")
            return
        smtp = {'server': settings[7], 'port': settings[8] or '587', 'username': settings[9], 'password': settings[10] or ''}
        invoice_number = self.invoice_number_input.text()
        subject = f"Invoice {invoice_number}"
        body = f"Dear {customer[0]},\n\nPlease find attached the invoice {invoice_number}.\n\nThank you."
        dialog = EmailDialog(self, customer[1], None, subject, body)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_email_data()
            self.save_invoice()
            pdf_path = None
            if data['attach_pdf']:
                result = self.pdf_generator.generate_invoice_pdf(invoice_number)
                if not result[1]:
                    pdf_path = result[0]
            err = EmailDialog.send_email(self, smtp, data['to'], data['subject'], data['body'], pdf_path)
            if err:
                QMessageBox.critical(self, "Error", f"Failed to send email: {err}")
            else:
                QMessageBox.information(self, "Success", "Email sent successfully!")

    def clear_quote_form(self):
        self.editing_quote_id = None
        self.quote_number_input.setReadOnly(False)
        self.quote_customer_combo.setCurrentIndex(0)
        self.quote_number_input.setText(f"Q-{datetime.now().strftime('%Y%m%d')}-001")
        self.quote_date_input.setDate(QDate.currentDate())
        self.quote_valid_until.setDate(QDate.currentDate().addDays(30))
        self.quote_notes.clear()
        self.quote_margin_rate.setValue(0)
        self.quote_discount.setValue(0)
        self.quote_authorized_by.clear()
        self.quote_designation.clear()
        self.quote_sig_date.setDate(QDate.currentDate())
        
        while self.quote_items_table.rowCount() > 0:
            self.quote_items_table.removeRow(0)
        
        self.update_quote_totals()
    
    def clear_invoice_form(self):
        self.editing_invoice_id = None
        self.invoice_number_input.setReadOnly(False)
        self.invoice_customer_combo.setCurrentIndex(0)
        self.invoice_number_input.setText(f"INV-{datetime.now().strftime('%Y%m%d')}-001")
        self.invoice_date_input.setDate(QDate.currentDate())
        self.invoice_due_date.setDate(QDate.currentDate().addDays(30))
        self.invoice_notes.clear()
        self.invoice_tax_rate.setValue(10)
        self.invoice_discount.setValue(0)
        self.invoice_authorized_by.clear()
        self.invoice_designation.clear()
        self.invoice_sig_date.setDate(QDate.currentDate())
        
        while self.invoice_items_table.rowCount() > 0:
            self.invoice_items_table.removeRow(0)
        
        self.update_invoice_totals()
    
    def load_records(self):
        self.records_table.setRowCount(0)
        
        search = f"%{self.search_input.text()}%"
        record_type = self.record_type_combo.currentText()
        
        queries = []
        params = []
        
        if record_type in ["All", "Quotations"]:
            queries.append("""
                SELECT quote_number, 'Quotation', c.name, q.date, q.total, q.status, 0, q.total
                FROM quotations q
                LEFT JOIN customers c ON q.customer_id = c.id
                WHERE (q.quote_number LIKE ? OR c.name LIKE ?)
            """)
            params.extend([search, search])
        
        if record_type in ["All", "Invoices"]:
            queries.append("""
                SELECT invoice_number, 'Invoice', c.name, i.date, i.total, i.status, i.paid_amount, i.total - i.paid_amount
                FROM invoices i
                LEFT JOIN customers c ON i.customer_id = c.id
                WHERE (i.invoice_number LIKE ? OR c.name LIKE ?)
            """)
            params.extend([search, search])
        
        if queries:
            union_query = " UNION ALL ".join(queries) + " ORDER BY 4 DESC"
            records = self.db.fetch_all(union_query, params)
            
            for row_idx, record in enumerate(records):
                self.records_table.insertRow(row_idx)
                for col_idx, value in enumerate(record):
                    if col_idx in [4, 6, 7]:
                        item = QTableWidgetItem(f"RM{value:.2f}")
                    else:
                        item = QTableWidgetItem(str(value))
                    self.records_table.setItem(row_idx, col_idx, item)
    
    def open_record(self, row, col):
        number = self.records_table.item(row, 0).text()
        record_type = self.records_table.item(row, 1).text()
        tabs = self.centralWidget().findChild(QTabWidget)
        if record_type == "Quotation":
            self.load_quotation_for_editing(number)
            tabs.setCurrentIndex(0)
        else:
            self.load_invoice_for_editing(number)
            tabs.setCurrentIndex(1)
    
    def open_selected_record(self):
        current_row = self.records_table.currentRow()
        if current_row >= 0:
            self.open_record(current_row, 0)
        else:
            QMessageBox.warning(self, "Warning", "Please select a record!")
    
    def load_quotation_for_editing(self, quote_number):
        quote = self.db.fetch_one(
            "SELECT id, customer_id, date, valid_until, notes, subtotal, tax_rate, tax_amount, discount, total FROM quotations WHERE quote_number = ?",
            (quote_number,))
        if not quote:
            QMessageBox.warning(self, "Error", "Quotation not found!")
            return
        items = self.db.fetch_all(
            "SELECT description, quantity, unit_price, amount FROM quotation_items WHERE quotation_id = ?", (quote[0],))
        
        self.clear_quote_form()
        self.editing_quote_id = quote[0]
        self.quote_number_input.setText(quote_number)
        self.quote_number_input.setReadOnly(True)
        
        idx = self.quote_customer_combo.findData(quote[1])
        if idx >= 0:
            self.quote_customer_combo.setCurrentIndex(idx)
        
        self.quote_date_input.setDate(QDate.fromString(quote[2], "yyyy-MM-dd"))
        self.quote_valid_until.setDate(QDate.fromString(quote[3], "yyyy-MM-dd"))
        self.quote_notes.setText(quote[4] or "")
        self.quote_margin_rate.setValue(quote[6])
        self.quote_discount.setValue(quote[7])
        
        for item in items:
            row = self.quote_items_table.rowCount()
            self.quote_items_table.insertRow(row)
            desc_item = QTableWidgetItem(item[0])
            self.quote_items_table.setItem(row, 0, desc_item)
            qty_spin = QDoubleSpinBox()
            qty_spin.setValue(item[1])
            qty_spin.setMaximum(1000000)
            qty_spin.valueChanged.connect(lambda: self.calculate_quote_item_amount(row))
            self.quote_items_table.setCellWidget(row, 1, qty_spin)
            price_spin = QDoubleSpinBox()
            price_spin.setValue(item[2])
            price_spin.setMaximum(1000000)
            price_spin.valueChanged.connect(lambda: self.calculate_quote_item_amount(row))
            self.quote_items_table.setCellWidget(row, 2, price_spin)
            amount_item = QTableWidgetItem(f"RM{item[3]:.2f}")
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
            self.quote_items_table.setItem(row, 3, amount_item)
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_quote_item(r))
            self.quote_items_table.setCellWidget(row, 4, delete_btn)
        
        self.update_quote_totals()
    
    def load_invoice_for_editing(self, invoice_number):
        invoice = self.db.fetch_one(
            "SELECT id, customer_id, date, due_date, notes, subtotal, tax_rate, tax_amount, discount, total FROM invoices WHERE invoice_number = ?",
            (invoice_number,))
        if not invoice:
            QMessageBox.warning(self, "Error", "Invoice not found!")
            return
        items = self.db.fetch_all(
            "SELECT description, quantity, unit_price, amount FROM invoice_items WHERE invoice_id = ?", (invoice[0],))
        
        self.clear_invoice_form()
        self.editing_invoice_id = invoice[0]
        self.invoice_number_input.setText(invoice_number)
        self.invoice_number_input.setReadOnly(True)
        
        idx = self.invoice_customer_combo.findData(invoice[1])
        if idx >= 0:
            self.invoice_customer_combo.setCurrentIndex(idx)
        
        self.invoice_date_input.setDate(QDate.fromString(invoice[2], "yyyy-MM-dd"))
        self.invoice_due_date.setDate(QDate.fromString(invoice[3], "yyyy-MM-dd"))
        self.invoice_notes.setText(invoice[4] or "")
        self.invoice_tax_rate.setValue(invoice[6])
        self.invoice_discount.setValue(invoice[7])
        
        for item in items:
            row = self.invoice_items_table.rowCount()
            self.invoice_items_table.insertRow(row)
            desc_item = QTableWidgetItem(item[0])
            self.invoice_items_table.setItem(row, 0, desc_item)
            qty_spin = QDoubleSpinBox()
            qty_spin.setValue(item[1])
            qty_spin.setMaximum(1000000)
            qty_spin.valueChanged.connect(lambda: self.calculate_invoice_item_amount(row))
            self.invoice_items_table.setCellWidget(row, 1, qty_spin)
            price_spin = QDoubleSpinBox()
            price_spin.setValue(item[2])
            price_spin.setMaximum(1000000)
            price_spin.valueChanged.connect(lambda: self.calculate_invoice_item_amount(row))
            self.invoice_items_table.setCellWidget(row, 2, price_spin)
            amount_item = QTableWidgetItem(f"RM{item[3]:.2f}")
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
            self.invoice_items_table.setItem(row, 3, amount_item)
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_invoice_item(r))
            self.invoice_items_table.setCellWidget(row, 4, delete_btn)
        
        self.update_invoice_totals()
    
    def delete_record(self):
        current_row = self.records_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a record!")
            return
        
        number = self.records_table.item(current_row, 0).text()
        record_type = self.records_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                    f"Are you sure you want to delete {record_type} {number}?",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if record_type == "Quotation":
                self.db.execute_query("DELETE FROM quotations WHERE quote_number = ?", (number,))
            else:
                self.db.execute_query("DELETE FROM invoices WHERE invoice_number = ?", (number,))
            
            self.load_records()
            QMessageBox.information(self, "Success", "Record deleted successfully!")
    
    def mark_as_paid(self):
        current_row = self.records_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select an invoice!")
            return
        
        record_type = self.records_table.item(current_row, 1).text()
        if record_type != "Invoice":
            QMessageBox.warning(self, "Warning", "Please select an invoice to mark as paid!")
            return
        
        number = self.records_table.item(current_row, 0).text()
        total = float(self.records_table.item(current_row, 4).text().replace('RM', ''))
        
        self.db.execute_query(
            "UPDATE invoices SET status = 'Paid', paid_amount = ? WHERE invoice_number = ?",
            (total, number)
        )
        
        self.load_records()
        QMessageBox.information(self, "Success", f"Invoice {number} marked as paid!")
    
    def export_selected_to_pdf(self):
        current_row = self.records_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a record!")
            return
        
        number = self.records_table.item(current_row, 0).text()
        record_type = self.records_table.item(current_row, 1).text()
        
        if record_type == "Quotation":
            self.print_quotation_to_pdf(number)
        else:
            self.print_invoice_to_pdf(number)
    
    def closeEvent(self, event):
        self.db.conn.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #0056b3;
        }
        QPushButton:pressed {
            background-color: #004085;
        }
        QTableWidget {
            gridline-color: #d0d0d0;
            border: 1px solid #d0d0d0;
        }
        QHeaderView::section {
            background-color: #e0e0e0;
            padding: 5px;
            border: 1px solid #d0d0d0;
            font-weight: bold;
        }
    """)
    
    window = QuotationInvoiceApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()