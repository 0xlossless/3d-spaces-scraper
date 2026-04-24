"""
Monitoring Dashboard.
Rich console output for data quality metrics, freshness alerts, and insights.
"""

import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)


class Dashboard:
    """Rich console dashboard for monitoring scraper health."""

    def __init__(self, db, quality_pipeline, analytics_engine):
        self.db = db
        self.quality = quality_pipeline
        self.analytics = analytics_engine
        self.console = Console()

    def show_overview(self):
        """Show comprehensive overview dashboard."""
        self.console.print(Panel.fit(
            Text("📊 3D Spaces Dataset Dashboard", style="bold cyan"),
            border_style="cyan",
        ))

        # Source Summary
        table = Table(title="📈 Source Summary", show_header=True, header_style="bold magenta")
        table.add_column("Source", style="cyan")
        table.add_column("Records", justify="right")
        table.add_column("License", style="green")
        table.add_column("Avg Quality", justify="right")
        table.add_column("Freshness", justify="right")

        for source, count in self.db.count_by_source().items():
            report = self.quality.generate_report(source)
            table.add_row(
                source,
                str(count),
                str(report.records_with_license),
                f"{report.avg_quality_score:.1f}",
                f"{report.freshness_days:.1f}d",
            )

        self.console.print(table)

        # License Distribution
        table = Table(title="📜 License Distribution", show_header=True, header_style="bold magenta")
        table.add_column("License", style="cyan")
        table.add_column("Count", justify="right")

        for row in self.db.conn.execute(
            "SELECT license, COUNT(*) as c FROM records WHERE license != '' GROUP BY license ORDER BY c DESC"
        ):
            table.add_row(row[0] or "(unknown)", str(row[1]))

        self.console.print(table)

        # Asset Type Distribution
        table = Table(title="🎮 Asset Types", show_header=True, header_style="bold magenta")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right")

        for row in self.db.conn.execute(
            "SELECT asset_type, COUNT(*) as c FROM records WHERE asset_type != '' GROUP BY asset_type ORDER BY c DESC"
        ):
            table.add_row(row[0], str(row[1]))

        self.console.print(table)

    def show_quality_report(self, source: str = None):
        """Show detailed quality report."""
        if source:
            report = self.quality.generate_report(source)
            self.console.print(Panel(
                f"[bold]{source}[/bold]\n"
                f"Total: {report.total_records}\n"
                f"With License: {report.records_with_license}\n"
                f"With Downloads: {report.records_with_downloads}\n"
                f"With Geometry: {report.records_with_geometry}\n"
                f"With Author: {report.records_with_author}\n"
                f"Avg Quality: {report.avg_quality_score}\n"
                f"Avg Downloads: {report.avg_download_count}\n"
                f"Freshness: {report.freshness_days} days",
                title=f"🔍 Quality Report: {source}",
                border_style="yellow",
            ))
        else:
            for source in self.db.count_by_source():
                self.show_quality_report(source)

    def show_anomalies(self, source: str = None):
        """Show data anomalies."""
        if source:
            anomalies = self.quality.detect_anomalies(source)
            if anomalies:
                table = Table(title=f"⚠️  Anomalies: {source}", show_header=True, header_style="bold red")
                table.add_column("Type", style="red")
                table.add_column("Details", style="yellow")

                for anomaly in anomalies:
                    table.add_row(anomaly.get("type", "unknown"), anomaly.get("message", ""))

                self.console.print(table)
            else:
                self.console.print(f"[green]✅ No anomalies detected for {source}[/green]")
        else:
            for source in self.db.count_by_source():
                self.show_anomalies(source)

    def show_insights(self):
        """Show dataset insights."""
        insights = self.analytics.get_insights()

        self.console.print(Panel.fit(
            Text("🧠 Dataset Insights", style="bold cyan"),
            border_style="cyan",
        ))

        table = Table(show_header=False, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Records", str(insights["total_records"]))
        table.add_row("CC0 (Free) Records", str(insights["cc0_records"]))
        table.add_row("With Geometry Data", str(insights["with_geometry"]))
        table.add_row("High Resolution (4K+)", str(insights["high_resolution"]))

        self.console.print(table)

        # Top Downloaded
        table = Table(title="🏆 Top 10 Most Downloaded", show_header=True, header_style="bold magenta")
        table.add_column("Title", style="cyan")
        table.add_column("Source", style="green")
        table.add_column("Downloads", justify="right")

        for title, source, downloads in insights["top_downloaded"][:10]:
            table.add_row(title[:40], source, str(downloads))

        self.console.print(table)

    def show_freshness_alerts(self, threshold_days: float = 7.0):
        """Show freshness alerts for stale data."""
        alerts = []

        for source, count in self.db.count_by_source().items():
            report = self.quality.generate_report(source)
            if report.freshness_days > threshold_days:
                alerts.append((source, report.freshness_days))

        if alerts:
            table = Table(title=f"⏰ Freshness Alerts (> {threshold_days} days)", show_header=True, header_style="bold red")
            table.add_column("Source", style="red")
            table.add_column("Days Old", justify="right")

            for source, days in alerts:
                table.add_row(source, f"{days:.1f}")

            self.console.print(table)
        else:
            self.console.print(f"[green]✅ All sources fresh (< {threshold_days} days)[/green]")
