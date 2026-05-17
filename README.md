# Quotation & Invoice Management System

A desktop application for creating, managing, and sending professional quotations and invoices. Built with PyQt5 and SQLite.

## Features

- **Draft Quotation** — Create quotations with line items, margin/profit calculation, margin allocation tracking, discount, and signature fields. Print draft PDFs showing margin details.
- **Create Quotation** — Generate clean client-ready PDFs (no margin shown) with a single click. Data can be transferred from the Draft tab.
- **Create Invoice** — Create invoices with due dates, tax, discount, signature fields. Track payment status (Unpaid/Paid/Overdue).
- **Manage Records** — Browse, search, edit, and delete all quotations and invoices in one place. Double-click to open for editing. Mark invoices as paid.
- **Manage Customers** — Add, edit, and delete customers. Deleting a customer cascades to remove all associated quotations, invoices, and line items.
- **PDF Generation** — Professional A4 PDFs with company header, logo, styled tables, alternating row colors, notes box, signature block, and multi-page support.
- **Email Integration** — Send quotations/invoices as PDF attachments via SMTP (Gmail, Outlook, etc.) directly from the application.
- **Company Settings** — Configure company name, address, logo, and SMTP credentials through the File menu.

## Requirements

- Python 3.7+
- PyQt5
- reportlab

Install dependencies:

```bash
pip install PyQt5 reportlab
```

## Usage

```bash
python quot_inv.py
```

The database file `business.db` is created automatically on first run.

## Configuration

Open **File > Company Settings** to set:

- **Company Info** — Name, address, phone, email, website, and logo image
- **SMTP Settings** — Server, port (default 587 for TLS), username, and password (required for sending emails)

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## Database

The app uses SQLite (`business.db`) with the following tables:

- `customers` — Customer contact information
- `quotations` — Quotation headers (number, dates, subtotal, margin, discount, total)
- `quotation_items` — Line items for each quotation
- `invoices` — Invoice headers (number, dates, subtotal, tax, discount, total, status, paid amount)
- `invoice_items` — Line items for each invoice
- `company_settings` — Company profile and SMTP configuration
