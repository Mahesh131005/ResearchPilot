import io
import textwrap
import datetime
from typing import Dict, Any, List, Optional
import pymupdf

class PDFReportGenerator:
    """
    Generates institutional-grade multi-page PDF research reports
    from structured ResearchReportSchema and job metadata.
    """

    PRIMARY_COLOR = (0.06, 0.10, 0.20)      # #0f1a33 dark navy
    SECONDARY_COLOR = (0.15, 0.35, 0.70)    # #2659b3 primary blue
    TEXT_COLOR = (0.12, 0.14, 0.18)         # #1f242e dark body text
    MUTED_TEXT = (0.40, 0.45, 0.55)         # #66738c secondary label
    ACCENT_BG = (0.95, 0.96, 0.98)          # #f2f5fa light section background
    BORDER_COLOR = (0.85, 0.88, 0.92)       # #d9e0eb card border
    
    # Status Colors
    STATUS_COLORS = {
        "supported": ((0.08, 0.50, 0.25), (0.90, 0.97, 0.92)),       # Green text, light green bg
        "partially_supported": ((0.75, 0.45, 0.05), (1.0, 0.96, 0.88)), # Amber text, light amber bg
        "unsupported": ((0.75, 0.15, 0.15), (1.0, 0.92, 0.92)),       # Red text, light red bg
        "contradictory": ((0.50, 0.15, 0.65), (0.96, 0.92, 1.0)),     # Purple text, light purple bg
    }

    def __init__(self):
        self.doc = pymupdf.open()
        self.page = None
        self.y = 50
        self.margin_x = 50
        self.page_width = 595.3  # A4 width
        self.page_height = 841.9 # A4 height
        self.content_width = 495.0
        self.max_y = 780

    def _new_page(self):
        self.page = self.doc.new_page(width=self.page_width, height=self.page_height)
        self.y = 55
        
        # Header on pages 2+
        if len(self.doc) > 1:
            self.page.insert_text(
                (self.margin_x, 35),
                "ResearchPilot | Analytical Intelligence Synthesis Report",
                fontname="helv",
                fontsize=8,
                color=self.MUTED_TEXT
            )
            self.page.draw_line(
                (self.margin_x, 42),
                (self.margin_x + self.content_width, 42),
                color=self.BORDER_COLOR,
                width=0.5
            )
            self.y = 65

    def _check_page_break(self, needed_space: float = 20):
        if self.page is None or self.y + needed_space > self.max_y:
            self._new_page()

    def _draw_text_line(
        self,
        text: str,
        x: float,
        fontname: str = "helv",
        fontsize: float = 10,
        color=None,
        leading: float = 14
    ):
        self._check_page_break(leading)
        self.page.insert_text(
            (x, self.y),
            text,
            fontname=fontname,
            fontsize=fontsize,
            color=color or self.TEXT_COLOR
        )
        self.y += leading

    def _draw_paragraph(
        self,
        text: str,
        x: float = 50,
        width_chars: int = 86,
        fontname: str = "helv",
        fontsize: float = 9.5,
        color=None,
        leading: float = 13.5,
        space_after: float = 8
    ):
        if not text:
            return
        paragraphs = text.split("\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                self.y += leading * 0.5
                continue
            wrapped_lines = textwrap.wrap(para, width=width_chars)
            for line in wrapped_lines:
                self._draw_text_line(line, x=x, fontname=fontname, fontsize=fontsize, color=color, leading=leading)
            self.y += space_after

    def _draw_section_header(self, title: str, section_num: Optional[int] = None):
        self._check_page_break(35)
        self.y += 10
        
        # Left blue accent pip
        self.page.draw_rect(
            pymupdf.Rect(self.margin_x, self.y - 12, self.margin_x + 4, self.y + 4),
            color=self.SECONDARY_COLOR,
            fill=self.SECONDARY_COLOR
        )
        
        heading_text = f"{section_num}. {title}" if section_num is not None else title
        self.page.insert_text(
            (self.margin_x + 12, self.y),
            heading_text,
            fontname="hebo",
            fontsize=12,
            color=self.PRIMARY_COLOR
        )
        self.y += 6
        
        self.page.draw_line(
            (self.margin_x, self.y),
            (self.margin_x + self.content_width, self.y),
            color=self.BORDER_COLOR,
            width=0.75
        )
        self.y += 14

    def build_report_pdf(self, report: Dict[str, Any], job: Optional[Dict[str, Any]] = None) -> bytes:
        self.doc = pymupdf.open()
        self._new_page()

        job_query = job.get("query", "Inquiry Analysis") if job else "Inquiry Analysis"
        job_id = str(job.get("id", "N/A")) if job else "N/A"
        date_str = datetime.datetime.now().strftime("%B %d, %Y - %H:%M UTC")

        # 1. Title Banner Card
        banner_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + 115)
        self.page.draw_rect(banner_rect, color=self.PRIMARY_COLOR, fill=self.PRIMARY_COLOR)

        self.page.insert_text(
            (self.margin_x + 18, self.y + 22),
            "RESEARCHPILOT | INSTITUTIONAL SYNTHESIS REPORT",
            fontname="hebo",
            fontsize=8.5,
            color=(0.65, 0.80, 1.0)
        )

        title = report.get("title", "Research Report")
        title_lines = textwrap.wrap(title, width=54)
        title_y = self.y + 44
        for tl in title_lines[:2]:
            self.page.insert_text(
                (self.margin_x + 18, title_y),
                tl,
                fontname="hebo",
                fontsize=14,
                color=(1.0, 1.0, 1.0)
            )
            title_y += 18

        # Metadata line in banner
        self.page.insert_text(
            (self.margin_x + 18, self.y + 98),
            f"Date: {date_str}   |   Job ID: {job_id[:12]}...   |   Orchestration: Multi-Agent RAG",
            fontname="helv",
            fontsize=8,
            color=(0.80, 0.85, 0.95)
        )
        self.y += 128

        # Inquiry Sub-banner
        inq_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + 36)
        self.page.draw_rect(inq_rect, color=self.BORDER_COLOR, fill=self.ACCENT_BG)
        self.page.insert_text(
            (self.margin_x + 10, self.y + 14),
            "RESEARCH INQUIRY:",
            fontname="hebo",
            fontsize=7.5,
            color=self.SECONDARY_COLOR
        )
        inq_wrapped = textwrap.wrap(job_query, width=95)
        self.page.insert_text(
            (self.margin_x + 10, self.y + 26),
            inq_wrapped[0] if inq_wrapped else "",
            fontname="helv",
            fontsize=8.5,
            color=self.TEXT_COLOR
        )
        self.y += 46

        # 2. Executive Summary
        self._draw_section_header("Executive Summary", 1)
        self._draw_paragraph(report.get("executive_summary", "No executive summary provided."))

        # 3. Industry Overview
        if report.get("industry_overview"):
            self._draw_section_header("Industry Overview", 2)
            self._draw_paragraph(report.get("industry_overview", ""))

        # 4. Key Research Findings
        findings = report.get("key_findings", [])
        if findings:
            self._draw_section_header("Key Research Findings", 3)
            for idx, kf in enumerate(findings, 1):
                self._check_page_break(25)
                # Bullet number
                self.page.insert_text(
                    (self.margin_x + 4, self.y),
                    f"{idx}.",
                    fontname="hebo",
                    fontsize=9.5,
                    color=self.SECONDARY_COLOR
                )
                self._draw_paragraph(kf, x=self.margin_x + 20, width_chars=82, space_after=6)

        # 5. Strategic Opportunities
        opps = report.get("opportunities", [])
        if opps:
            self._draw_section_header("Strategic Opportunities", 4)
            for opp in opps:
                self._check_page_break(20)
                self.page.insert_text((self.margin_x + 6, self.y), "•", fontname="hebo", fontsize=11, color=self.SECONDARY_COLOR)
                self._draw_paragraph(opp, x=self.margin_x + 20, width_chars=82, space_after=5)

        # 6. Risks and Regulatory Challenges
        risks = report.get("risks_and_challenges", [])
        if risks:
            self._draw_section_header("Risks, Governance & Regulatory Challenges", 5)
            for rk in risks:
                self._check_page_break(20)
                self.page.insert_text((self.margin_x + 6, self.y), "▲", fontname="hebo", fontsize=8, color=(0.8, 0.2, 0.1))
                self._draw_paragraph(rk, x=self.margin_x + 20, width_chars=82, space_after=5)

        # 7. Contradictory Findings
        contradictions = report.get("contradictory_findings", [])
        if contradictions:
            self._draw_section_header("Contradictory Findings & Discrepancies", 6)
            for cf in contradictions:
                self._check_page_break(20)
                self.page.insert_text((self.margin_x + 6, self.y), "⚠", fontname="hebo", fontsize=10, color=(0.7, 0.3, 0.1))
                self._draw_paragraph(cf, x=self.margin_x + 20, width_chars=82, space_after=5)

        # 8. Future Outlook
        if report.get("future_outlook"):
            sec_num = 7 if contradictions else 6
            self._draw_section_header("Strategic Future Outlook", sec_num)
            self._draw_paragraph(report.get("future_outlook", ""))

        # 9. Fact-Checked Claims Audit
        claims = report.get("claims", [])
        if claims:
            sec_num = (8 if contradictions else 7)
            self._draw_section_header("Fact-Checked Claims Audit Matrix", sec_num)
            
            for c in claims:
                self._check_page_break(65)
                status = c.get("verification_status", "unsupported").lower()
                fg_col, bg_col = self.STATUS_COLORS.get(status, self.STATUS_COLORS["unsupported"])
                
                # Claim card container start
                card_start_y = self.y
                self.y += 14
                
                # Status pill
                pill_rect = pymupdf.Rect(self.margin_x + 6, self.y - 10, self.margin_x + 130, self.y + 4)
                self.page.draw_rect(pill_rect, color=fg_col, fill=bg_col, width=0.5)
                self.page.insert_text(
                    (self.margin_x + 12, self.y),
                    f"{status.upper().replace('_', ' ')}  ({int(c.get('confidence_score', 0) * 100)}%)",
                    fontname="hebo",
                    fontsize=7.5,
                    color=fg_col
                )
                self.y += 14
                
                # Claim text
                self._draw_paragraph(
                    c.get("claim_text", ""),
                    x=self.margin_x + 10,
                    width_chars=80,
                    fontname="hebo",
                    fontsize=9,
                    color=self.PRIMARY_COLOR,
                    space_after=4
                )
                
                # Reasoning
                if c.get("reasoning"):
                    self._draw_paragraph(
                        f"Audit: {c.get('reasoning')}",
                        x=self.margin_x + 10,
                        width_chars=82,
                        fontname="helv",
                        fontsize=8.5,
                        color=self.MUTED_TEXT,
                        space_after=4
                    )
                
                # Source
                if c.get("citation_source"):
                    self._draw_paragraph(
                        f"Source: {c.get('citation_source')}",
                        x=self.margin_x + 10,
                        width_chars=82,
                        fontname="helv",
                        fontsize=8,
                        color=self.SECONDARY_COLOR,
                        space_after=8
                    )
                
                card_end_y = self.y
                # Draw left vertical accent bar for claim card
                self.page.draw_rect(
                    pymupdf.Rect(self.margin_x, card_start_y, self.margin_x + 3, card_end_y - 4),
                    color=fg_col,
                    fill=fg_col
                )
                self.y += 8

        # 10. References & Citations Directory
        refs = report.get("references", [])
        if refs:
            sec_num = (9 if contradictions else 8)
            self._draw_section_header("References & Evidentiary Provenance", sec_num)
            
            for r in refs:
                self._check_page_break(35)
                label = r.get("citation_label", "[Ref]")
                self.page.insert_text(
                    (self.margin_x + 4, self.y),
                    label,
                    fontname="hebo",
                    fontsize=8.5,
                    color=self.SECONDARY_COLOR
                )
                title_line = r.get("title", "External Reference")
                self._draw_paragraph(title_line, x=self.margin_x + 55, width_chars=75, fontname="hebo", fontsize=8.5, space_after=2)
                
                if r.get("url"):
                    self._draw_paragraph(f"URL: {r.get('url')}", x=self.margin_x + 55, width_chars=80, fontsize=7.5, color=self.SECONDARY_COLOR, space_after=2)
                elif r.get("page_number"):
                    self._draw_paragraph(f"PDF Document Reference: Page {r.get('page_number')}", x=self.margin_x + 55, width_chars=80, fontsize=7.5, color=self.MUTED_TEXT, space_after=2)
                
                if r.get("snippet"):
                    snippet = f'"{r.get("snippet").strip()[:180]}..."'
                    self._draw_paragraph(snippet, x=self.margin_x + 55, width_chars=80, fontname="helv", fontsize=8, color=self.MUTED_TEXT, space_after=8)

        # 11. Footers on all pages
        total_pages = len(self.doc)
        for idx, p in enumerate(self.doc, 1):
            p.draw_line(
                (self.margin_x, self.page_height - 35),
                (self.margin_x + self.content_width, self.page_height - 35),
                color=self.BORDER_COLOR,
                width=0.5
            )
            p.insert_text(
                (self.margin_x, self.page_height - 24),
                f"ResearchPilot Intelligence Platform  •  Strict Evidentiary Provenance",
                fontname="helv",
                fontsize=7.5,
                color=self.MUTED_TEXT
            )
            page_str = f"Page {idx} of {total_pages}"
            p.insert_text(
                (self.margin_x + self.content_width - 55, self.page_height - 24),
                page_str,
                fontname="helv",
                fontsize=7.5,
                color=self.MUTED_TEXT
            )

        pdf_bytes = self.doc.write()
        self.doc.close()
        return pdf_bytes

