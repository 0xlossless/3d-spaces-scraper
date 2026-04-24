"""
Pydantic data models for 3D Spaces Dataset.
Provides schema validation, type checking, and serialization.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Record(BaseModel):
    """Validated 3D asset record with full schema enforcement."""

    # Core fields
    id: str = Field(..., description="Unique record ID")
    source: str = Field(..., min_length=1, description="Data source")
    title: str = Field(..., min_length=1, description="Asset title")
    description: str = Field(default="", max_length=2000, description="Asset description")
    tags: list[str] = Field(default_factory=list, max_length=50, description="Tags")
    genre: str = Field(default="", description="Genre/category")
    engine: str = Field(default="", description="3D engine")
    platform: str = Field(default="multiplatform", description="Platform")
    file_size: str = Field(default="", description="Human-readable file size")
    link: str = Field(..., min_length=1, description="Asset URL")
    thumbnail_url: str = Field(default="", description="Thumbnail URL")
    scraped_at: str = Field(..., description="Scrape timestamp")
    author: str = Field(default="", description="Creator name")
    game_id: str = Field(default="", description="Source-specific ID")

    # License & usage
    license: str = Field(default="", description="License type")
    download_count: int = Field(default=0, ge=0, description="Download count")
    view_count: int = Field(default=0, ge=0, description="View count")
    like_count: int = Field(default=0, ge=0, description="Like/favorite count")
    rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Rating (0-5)")
    price: str = Field(default="", description="Price or 'free'")
    release_date: Optional[str] = Field(default=None, description="Release date (ISO)")
    created_at: Optional[str] = Field(default=None, description="Created timestamp")
    updated_at: Optional[str] = Field(default=None, description="Updated timestamp")

    # 3D geometry & technical
    polycount: int = Field(default=0, ge=0, description="Triangle/vertex count")
    texel_density: float = Field(default=0.0, ge=0.0, description="Texels per unit")
    dimensions_x: float = Field(default=0.0, description="Width in mm")
    dimensions_y: float = Field(default=0.0, description="Height in mm")
    dimensions_z: float = Field(default=0.0, description="Depth in mm")
    max_resolution_w: int = Field(default=0, ge=0, description="Max resolution width")
    max_resolution_h: int = Field(default=0, ge=0, description="Max resolution height")
    file_formats: list[str] = Field(default_factory=list, description="Supported formats")
    asset_type: str = Field(default="", description="model/hdri/texture/material/etc")
    creation_method: str = Field(default="", description="PBRPhotogrammetry/3DSoftware/etc")
    popularity_score: float = Field(default=0.0, ge=0.0, description="Computed popularity")

    # Taxonomy & attribution
    categories: list[str] = Field(default_factory=list, description="Categories")
    authors: list[str] = Field(default_factory=list, description="Contributor names")
    sponsors: list[str] = Field(default_factory=list, description="Sponsor IDs")
    files_hash: str = Field(default="", description="SHA1 hash for versioning")
    location: str = Field(default="", description="GPS coords or location")
    square_footage: str = Field(default="", description="Area coverage")
    room_count: int = Field(default=0, ge=0, description="Number of rooms")
    version: str = Field(default="", description="Software or asset version")
    is_downloadable: int = Field(default=0, ge=0, le=1, description="Downloadable flag")
    engine_detected: str = Field(default="", description="Detected engine")

    # Computed features
    quality_score: float = Field(default=0.0, description="Computed quality metric")
    popularity_tier: str = Field(default="unknown", description="low/medium/high/viral")

    @field_validator("link")
    @classmethod
    def validate_link(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Link must be a valid HTTP(S) URL")
        return v

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://", "//")):
            raise ValueError("Thumbnail URL must be valid")
        return v

    def compute_quality_score(self) -> float:
        """Compute a quality score (0-100) based on available metadata."""
        score = 0.0

        # Has description (+10)
        if self.description:
            score += 10

        # Has tags (+10, up to 20 for 10+ tags)
        tag_score = min(len(self.tags) * 2, 20)
        score += tag_score

        # Has author (+10)
        if self.author or self.authors:
            score += 10

        # Has license (+10)
        if self.license:
            score += 10

        # Has download count (+10)
        if self.download_count > 0:
            score += 10

        # Has geometry data (+10)
        if self.polycount > 0:
            score += 10

        # Has resolution data (+10)
        if self.max_resolution_w > 0 and self.max_resolution_h > 0:
            score += 10

        # Has file formats (+10)
        if self.file_formats:
            score += 10

        return min(score, 100.0)

    def compute_popularity_tier(self) -> str:
        """Classify popularity into tiers."""
        score = self.popularity_score or (self.download_count + self.view_count + self.like_count)

        if score >= 50000:
            return "viral"
        elif score >= 10000:
            return "high"
        elif score >= 1000:
            return "medium"
        elif score > 0:
            return "low"
        return "unknown"

    def model_post_init(self, __context) -> None:
        """Compute derived fields after initialization."""
        self.quality_score = self.compute_quality_score()
        self.popularity_tier = self.compute_popularity_tier()

    def to_dict(self) -> dict:
        """Convert to dict for database insertion."""
        return self.model_dump()


class ScrapeSummary(BaseModel):
    """Summary of a scrape run."""

    source: str
    total_records: int
    new_records: int
    skipped_records: int
    errors: int = 0
    duration_seconds: float = 0.0
    scraped_at: str = ""


class DataQualityReport(BaseModel):
    """Data quality metrics for a source."""

    source: str
    total_records: int
    records_with_license: int = 0
    records_with_downloads: int = 0
    records_with_geometry: int = 0
    records_with_author: int = 0
    records_with_timestamp: int = 0
    records_with_tags: int = 0
    avg_quality_score: float = 0.0
    avg_download_count: float = 0.0
    freshness_days: float = 0.0  # Days since last scrape
