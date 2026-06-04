from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from config.settings import EmailConfig
from core.analytics import ReportData


def _build_summary(report: ReportData) -> str:
    lines = [
        f"Period:    {report.period_label}",
        f"",
        f"Balance:   {report.opening_balance:,.2f} → {report.closing_balance:,.2f}  "
        f"({'+'if report.balance_change >= 0 else ''}{report.balance_change:,.2f})",
        f"Income:    {report.total_income:,.2f}",
        f"Expenses:  {report.total_expenses:,.2f}",
        f"Net:       {report.real_net:+,.2f}",
    ]
    if report.pending_cc:
        lines.append(f"Pending CC: {report.pending_cc:,.2f}")
    if report.categories:
        lines += ["", "Top categories:"]
        for cat in report.categories[:5]:
            lines.append(f"  {cat.name}  {cat.total:,.2f}")
    return "\n".join(lines)


def send_report(html_path: Path, report: ReportData, config: EmailConfig) -> None:
    subject = f"Leumi Report — {report.period_label}"
    body = _build_summary(report)
    html_bytes = html_path.read_bytes()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.sender
    msg["To"] = config.recipient
    msg.set_content(body)
    msg.add_attachment(
        html_bytes,
        maintype="text",
        subtype="html",
        filename=html_path.name,
    )

    if config.port == 465:
        with smtplib.SMTP_SSL(config.host, config.port) as smtp:
            smtp.login(config.user, config.password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(config.host, config.port) as smtp:
            smtp.starttls()
            smtp.login(config.user, config.password)
            smtp.send_message(msg)

    print(f"[email] report sent to {config.recipient}")
