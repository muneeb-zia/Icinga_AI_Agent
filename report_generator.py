"""
Custom Enterprise Report Generator (PDF & Multi-Tab Excel with Native Formulas & Visualizations)
Generates:
1. Branded Executive PDF Report (ReportLab) with KPI scorecards, embedded charts, and RCA tables.
2. Multi-Tab Excel (.xlsx) Workbook (openpyxl) with dynamic native formulas and SLA compliance tracking.
"""

import sys
import os
import time
from typing import List, Dict, Any, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# 1. CHART GENERATOR FOR REPORTS
# =============================================================================

def generate_report_chart_images(output_dir: str) -> Dict[str, str]:
    """Generates high-resolution chart images to embed into PDF reports."""
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Incident Breakdown Pie Chart
    chart1_path = os.path.join(output_dir, "report_incident_pie.png")
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=200)
    labels = ['Network (25%)', 'Database (35%)', 'Memory/OOM (20%)', 'Web/Proxy (20%)']
    sizes = [25, 35, 20, 20]
    colors = ['#3498DB', '#E74C3C', '#F39C12', '#2ECC71']
    explode = (0, 0.08, 0, 0)
    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.0f%%', startangle=140,
           textprops={'fontsize': 8, 'fontweight': 'bold'})
    ax.set_title("30-Day Incident Severity & Category Breakdown", fontsize=10, fontweight='bold', pad=10)
    plt.tight_layout()
    plt.savefig(chart1_path)
    plt.close()

    # 2. Daily Availability SLA Trend Bar Chart
    chart2_path = os.path.join(output_dir, "report_uptime_trend.png")
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    days = [f"Day {i}" for i in range(1, 15)]
    uptime = [99.98, 100.0, 99.95, 100.0, 99.92, 100.0, 100.0, 99.88, 100.0, 99.99, 100.0, 100.0, 99.96, 100.0]
    ax.plot(days, uptime, marker='o', color='#2B6CB0', linewidth=2, markersize=5)
    ax.axhline(99.90, color='#E53E3E', linestyle='--', linewidth=1.2, label='SLA Target (99.90%)')
    ax.set_ylim(99.80, 100.05)
    ax.set_ylabel("Uptime Availability (%)", fontsize=8, fontweight='bold')
    ax.set_title("14-Day Rolling Service Availability Trend", fontsize=10, fontweight='bold', pad=10)
    ax.set_xticklabels(days, rotation=45, ha='right', fontsize=7)
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(chart2_path)
    plt.close()

    return {"pie": chart1_path, "uptime": chart2_path}


# =============================================================================
# 2. BRANDED ENTERPRISE PDF GENERATOR (ReportLab)
# =============================================================================

class EnterprisePDFReportGenerator:
    """Generates C-Suite and client-ready branded SLA & Incident Health PDF reports."""

    @classmethod
    def generate_pdf(
        cls,
        client_name: str,
        report_title: str,
        output_filename: str = "enterprise_sla_report.pdf",
        time_period: str = "Last 30 Days"
    ) -> str:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        pdf_path = os.path.abspath(output_filename)
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        primary_color = colors.HexColor("#1A365D")  # Deep Corporate Navy
        accent_color = colors.HexColor("#2B6CB0")   # Executive Slate Blue
        text_dark = colors.HexColor("#2D3748")

        # Custom Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=primary_color,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'ReportSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#718096")
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            textColor=primary_color,
            spaceBefore=12,
            spaceAfter=6
        )
        body_text = ParagraphStyle(
            'BodyTextCustom',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=text_dark
        )
        kpi_title = ParagraphStyle('KPITitle', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor("#4A5568"), alignment=1)
        kpi_val = ParagraphStyle('KPIVal', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=accent_color, alignment=1)

        story = []

        # 1. Header & Title Banner
        story.append(Paragraph(f"<b>{report_title}</b>", title_style))
        story.append(Paragraph(f"Client: <b>{client_name}</b> | Reporting Window: <b>{time_period}</b> | Generated: <b>{time.strftime('%Y-%m-%d %H:%M UTC')}</b>", subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=2, color=primary_color, spaceAfter=12))

        # 2. Executive Summary Block
        summary_p = Paragraph(
            f"This autonomous observability audit details system availability, mean-time-to-resolution (MTTR), "
            f"and root-cause analyses for <b>{client_name}</b>. During the past 30 days, global platform uptime "
            f"achieved <b>99.96%</b>, exceeding the contractual service level agreement target of <b>99.90%</b>. "
            f"Autonomous AI agent actions mitigated <b>85%</b> of critical alerts within sub-minute intervals.",
            body_text
        )
        story.append(summary_p)
        story.append(Spacer(1, 10))

        # 3. KPI Scorecard Table
        kpi_data = [
            [
                Paragraph("PLATFORM AVAILABILITY", kpi_title),
                Paragraph("TOTAL INCIDENTS", kpi_title),
                Paragraph("MEAN TIME TO RESOLVE", kpi_title),
                Paragraph("SLA COMPLIANCE", kpi_title)
            ],
            [
                Paragraph("99.96%", kpi_val),
                Paragraph("14", kpi_val),
                Paragraph("11.8 min", kpi_val),
                Paragraph("100% MET", kpi_val)
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[1.85*inch]*4)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # 4. Embedded Visualizations
        chart_files = generate_report_chart_images(os.path.dirname(pdf_path))
        img_table = Table([
            [
                Image(chart_files["uptime"], width=4.3*inch, height=2.0*inch),
                Image(chart_files["pie"], width=3.1*inch, height=2.0*inch)
            ]
        ], colWidths=[4.4*inch, 3.2*inch])
        img_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(img_table)
        story.append(Spacer(1, 10))

        # 5. Incident & Autonomous Root-Cause Analysis Table
        story.append(Paragraph("<b>Recent Critical Incidents & Autonomous Root-Cause Analysis (RCA)</b>", section_heading))

        incident_headers = ["Incident ID", "Host / Service", "Duration", "RCA & Autonomous Remediation", "Status"]
        table_rows = [
            [Paragraph(f"<b>{h}</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=1)) for h in incident_headers]
        ]

        sample_incidents = [
            ("INC-8041", "web-prod-01\ncheck_disk /var/log", "8 min", "Log bloat in journalctl. AI Agent executed vacuum prune and freed 8.2 GB storage.", "RESOLVED"),
            ("INC-8042", "db-mysql-primary\ncheck_mysql", "14 min", "Max connections pool saturation (500). Agent terminated idle sleep threads.", "RESOLVED"),
            ("INC-8043", "api-gateway-02\nHTTP 502 Proxy", "6 min", "Upstream PHP-FPM socket crash. Autonomous restart restored API availability.", "RESOLVED"),
            ("INC-8044", "k8s-worker-03\nOOMKilled Pod", "12 min", "Container exceeded 2GB memory ceiling. Rollout restart triggered with cache drop.", "RESOLVED"),
        ]

        for inc_id, host_svc, dur, rca, status in sample_incidents:
            table_rows.append([
                Paragraph(f"<b>{inc_id}</b>", ParagraphStyle('T1', fontSize=7.5, fontName='Helvetica-Bold')),
                Paragraph(host_svc.replace("\n", "<br/>"), ParagraphStyle('T2', fontSize=7.5)),
                Paragraph(dur, ParagraphStyle('T3', fontSize=7.5, alignment=1)),
                Paragraph(rca, ParagraphStyle('T4', fontSize=7.5)),
                Paragraph(f"<b>{status}</b>", ParagraphStyle('T5', fontSize=7.5, textColor=colors.HexColor("#27AE60"), alignment=1))
            ])

        inc_table = Table(table_rows, colWidths=[1.1*inch, 1.6*inch, 0.8*inch, 3.1*inch, 0.9*inch])
        inc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(inc_table)

        doc.build(story)
        return pdf_path


# =============================================================================
# 3. MULTI-TAB EXCEL WORKBOOK GENERATOR (openpyxl with Native Formulas)
# =============================================================================

class EnterpriseExcelReportGenerator:
    """Generates a professional 4-tab Excel workbook with dynamic formulas and styles."""

    @classmethod
    def generate_excel(
        cls,
        client_name: str,
        output_filename: str = "enterprise_sla_report.xlsx"
    ) -> str:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()

        # Define Styles
        header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=16, bold=True, color="1A365D")
        bold_font = Font(name="Calibri", size=11, bold=True)
        regular_font = Font(name="Calibri", size=10)
        kpi_val_font = Font(name="Calibri", size=14, bold=True, color="2B6CB0")
        
        thin_border = Border(
            left=Side(style='thin', color='CBD5E0'),
            right=Side(style='thin', color='CBD5E0'),
            top=Side(style='thin', color='CBD5E0'),
            bottom=Side(style='thin', color='CBD5E0')
        )
        green_fill = PatternFill(start_color="E6FFFA", end_color="E6FFFA", fill_type="solid")
        green_font = Font(name="Calibri", size=10, bold=True, color="234E52")

        # ---------------------------------------------------------------------
        # TAB 1: EXECUTIVE DASHBOARD
        # ---------------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "Executive Dashboard"
        ws1.views.sheetView[0].showGridLines = True

        ws1["A1"] = f"ENTERPRISE SLA & INCIDENT HEALTH DASHBOARD"
        ws1["A1"].font = title_font
        ws1["A2"] = f"Client: {client_name} | Generated: {time.strftime('%Y-%m-%d %H:%M UTC')}"
        ws1["A2"].font = Font(name="Calibri", size=10, italic=True, color="718096")

        # KPI Summary Cards
        kpi_headers = ["Metric", "Actual Value", "SLA Target", "Compliance Status"]
        for col_num, h in enumerate(kpi_headers, 1):
            cell = ws1.cell(row=5, column=col_num, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        kpis = [
            ("Service Availability (Uptime)", "=AVERAGE('SLA Compliance'!B3:B16)", ">= 99.90%", "=IF(B6>=99.90, \"MET\", \"BREACHED\")"),
            ("Total Monitored Incidents", "=COUNTA('Incident Log'!A3:A10)", "<= 25", "=IF(B7<=25, \"MET\", \"BREACHED\")"),
            ("Mean Time to Resolution (MTTR)", "=AVERAGE('Incident Log'!F3:F10)", "<= 30.0 min", "=IF(B8<=30, \"MET\", \"BREACHED\")"),
            ("P1 Outages Total", "=COUNTIF('Incident Log'!E3:E10, \"P1 - CRITICAL\")", "0 Outages", "=IF(B9=0, \"MET\", \"BREACHED\")")
        ]

        for r_idx, (m, val_formula, target, status_formula) in enumerate(kpis, 6):
            c1 = ws1.cell(row=r_idx, column=1, value=m)
            c2 = ws1.cell(row=r_idx, column=2, value=val_formula)
            c3 = ws1.cell(row=r_idx, column=3, value=target)
            c4 = ws1.cell(row=r_idx, column=4, value=status_formula)
            for c in [c1, c2, c3, c4]:
                c.font = regular_font
                c.border = thin_border
            c2.font = bold_font
            c2.number_format = '0.00'
            c4.font = green_font
            c4.fill = green_fill
            c4.alignment = Alignment(horizontal="center")

        # ---------------------------------------------------------------------
        # TAB 2: HOST TELEMETRY & STATUS
        # ---------------------------------------------------------------------
        ws2 = wb.create_sheet(title="Host Status")
        ws2.views.sheetView[0].showGridLines = True

        ws2["A1"] = f"Host Fleet Health & Monitored Services"
        ws2["A1"].font = title_font

        headers2 = ["Hostname", "IP Address", "Tier", "CPU Load (%)", "Memory (%)", "Disk (%)", "State", "Response Time (ms)"]
        for col_num, h in enumerate(headers2, 1):
            cell = ws2.cell(row=3, column=col_num, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        hosts_data = [
            ("web-prod-01.internal", "10.0.1.11", "Web Tier", 45.2, 62.1, 74.5, "OK", 12.4),
            ("web-prod-02.internal", "10.0.1.12", "Web Tier", 48.0, 64.3, 76.0, "OK", 14.1),
            ("web-prod-03.internal", "10.0.1.13", "Web Tier", 42.1, 59.8, 71.2, "OK", 11.8),
            ("db-mysql-primary.internal", "10.0.2.21", "Database Tier", 68.4, 82.5, 84.1, "OK", 4.2),
            ("db-mysql-replica-01.internal", "10.0.2.22", "Database Tier", 54.1, 78.0, 83.9, "OK", 5.1),
            ("db-mysql-replica-02.internal", "10.0.2.23", "Database Tier", 52.9, 77.2, 83.8, "OK", 4.8),
            ("payment-api-01.internal", "10.0.3.31", "Payment Tier", 38.0, 51.4, 45.0, "OK", 22.5),
            ("k8s-worker-01.internal", "10.0.4.41", "Compute Tier", 81.2, 88.4, 62.0, "WARNING", 18.2),
        ]

        for r_idx, row in enumerate(hosts_data, 4):
            for c_idx, val in enumerate(row, 1):
                cell = ws2.cell(row=r_idx, column=c_idx, value=val)
                cell.font = regular_font
                cell.border = thin_border
                if c_idx in [4, 5, 6, 8]:
                    cell.alignment = Alignment(horizontal="right")

        # ---------------------------------------------------------------------
        # TAB 3: INCIDENT LOG & DYNAMIC MTTR FORMULAS
        # ---------------------------------------------------------------------
        ws3 = wb.create_sheet(title="Incident Log")
        ws3.views.sheetView[0].showGridLines = True

        ws3["A1"] = f"Incident Audit Log & Resolution Time Tracking"
        ws3["A1"].font = title_font

        headers3 = ["Incident ID", "Timestamp", "Host", "Service", "Severity", "Duration (min)", "Root Cause (RCA)", "Remediation Script"]
        for col_num, h in enumerate(headers3, 1):
            cell = ws3.cell(row=2, column=col_num, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        incidents = [
            ("INC-8041", "2026-08-12 04:12", "web-prod-01", "check_disk", "P2 - MEDIUM", 8.0, "Log bloat in /var/log", "journalctl --vacuum-time=2d"),
            ("INC-8042", "2026-08-14 11:30", "db-mysql-primary", "check_mysql", "P1 - CRITICAL", 14.0, "Max connections exhausted (500)", "KILL idle threads; SET max_conn=800"),
            ("INC-8043", "2026-08-18 09:15", "payment-api-01", "HTTP 502", "P2 - MEDIUM", 6.0, "PHP-FPM socket crash", "systemctl restart php-fpm"),
            ("INC-8044", "2026-08-20 22:45", "k8s-worker-01", "check_mem", "P1 - CRITICAL", 12.0, "OOM Killer terminated Pod", "kubectl rollout restart deployment"),
            ("INC-8045", "2026-08-22 14:02", "sw-core-01", "check_ping", "P2 - MEDIUM", 18.0, "Transceiver CRC packet drop", "Port failover to secondary trunk"),
            ("INC-8046", "2026-08-24 16:50", "web-prod-03", "check_ssl_cert", "P3 - LOW", 10.0, "Certificate expiry warning", "certbot renew --force-renewal"),
            ("INC-8047", "2026-08-26 08:20", "db-mysql-replica-01", "check_mysql", "P2 - MEDIUM", 15.0, "Replication thread lag", "START SLAVE; sync binlog"),
            ("INC-8048", "2026-08-27 19:10", "k8s-worker-01", "check_docker", "P2 - MEDIUM", 11.0, "Dangling container accumulation", "docker system prune -af")
        ]

        for r_idx, row in enumerate(incidents, 3):
            for c_idx, val in enumerate(row, 1):
                cell = ws3.cell(row=r_idx, column=c_idx, value=val)
                cell.font = regular_font
                cell.border = thin_border
                if c_idx == 6:
                    cell.alignment = Alignment(horizontal="right")
                    cell.number_format = '0.0'

        # Formula Summary Rows
        last_row = len(incidents) + 3
        ws3.cell(row=last_row, column=5, value="Average MTTR:").font = bold_font
        avg_cell = ws3.cell(row=last_row, column=6, value=f"=AVERAGE(F3:F{last_row-1})")
        avg_cell.font = bold_font
        avg_cell.number_format = '0.0 "min"'

        # ---------------------------------------------------------------------
        # TAB 4: SLA COMPLIANCE
        # ---------------------------------------------------------------------
        ws4 = wb.create_sheet(title="SLA Compliance")
        ws4.views.sheetView[0].showGridLines = True

        ws4["A1"] = f"Daily Service Level Agreement (SLA) Calculations"
        ws4["A1"].font = title_font

        headers4 = ["Day / Date", "Daily Uptime (%)", "Target SLA (%)", "Downtime (min)", "SLA Met?"]
        for col_num, h in enumerate(headers4, 1):
            cell = ws4.cell(row=2, column=col_num, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        sla_data = [
            ("2026-08-14", 99.98, 99.90, 0.28),
            ("2026-08-15", 100.00, 99.90, 0.00),
            ("2026-08-16", 99.95, 99.90, 0.72),
            ("2026-08-17", 100.00, 99.90, 0.00),
            ("2026-08-18", 99.92, 99.90, 1.15),
            ("2026-08-19", 100.00, 99.90, 0.00),
            ("2026-08-20", 100.00, 99.90, 0.00),
            ("2026-08-21", 99.88, 99.90, 1.72),
            ("2026-08-22", 100.00, 99.90, 0.00),
            ("2026-08-23", 99.99, 99.90, 0.14),
            ("2026-08-24", 100.00, 99.90, 0.00),
            ("2026-08-25", 100.00, 99.90, 0.00),
            ("2026-08-26", 99.96, 99.90, 0.57),
            ("2026-08-27", 100.00, 99.90, 0.00),
        ]

        for r_idx, (d, upt, tgt, dt) in enumerate(sla_data, 3):
            c1 = ws4.cell(row=r_idx, column=1, value=d)
            c2 = ws4.cell(row=r_idx, column=2, value=upt)
            c3 = ws4.cell(row=r_idx, column=3, value=tgt)
            c4 = ws4.cell(row=r_idx, column=4, value=dt)
            # Native Excel Formula for SLA compliance check
            c5 = ws4.cell(row=r_idx, column=5, value=f'=IF(B{r_idx}>=C{r_idx}, "YES", "NO")')

            for c in [c1, c2, c3, c4, c5]:
                c.font = regular_font
                c.border = thin_border
            c2.number_format = '0.00"%"'
            c3.number_format = '0.00"%"'
            c4.number_format = '0.00'
            c5.font = green_font
            c5.alignment = Alignment(horizontal="center")

        # Auto-adjust column widths across all worksheets
        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

        excel_path = os.path.abspath(output_filename)
        wb.save(excel_path)
        return excel_path


if __name__ == "__main__":
    print("================================================================================")
    print("🚀 TESTING ENTERPRISE REPORT GENERATOR (PDF & MULTI-TAB EXCEL)")
    print("================================================================================")

    client = "E-Commerce Global Retail Corp"

    print("\n1. Generating Executive Branded PDF Report...")
    pdf_out = EnterprisePDFReportGenerator.generate_pdf(client, "Monthly SLA & Infrastructure Health Audit", "enterprise_sla_report.pdf")
    print(f"✅ Generated PDF Report: {pdf_out} ({os.path.getsize(pdf_out)} bytes)")

    print("\n2. Generating Multi-Tab Excel (.xlsx) Workbook with Native Formulas...")
    excel_out = EnterpriseExcelReportGenerator.generate_excel(client, "enterprise_sla_report.xlsx")
    print(f"✅ Generated Excel Workbook: {excel_out} ({os.path.getsize(excel_out)} bytes)")
