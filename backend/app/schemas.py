from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    role: str
    organization_id: str


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    location: str | None = Field(default=None, max_length=240)


class SiteOut(SiteCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    created_at: datetime


class StationCreate(BaseModel):
    site_id: str
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = None
    expected_cycle_seconds: float | None = Field(default=None, gt=0, le=86400)


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    site_id: str
    name: str
    code: str
    description: str | None
    expected_cycle_seconds: float | None
    is_active: bool
    created_at: datetime


class CameraCreate(BaseModel):
    station_id: str
    name: str = Field(min_length=1, max_length=160)
    source_type: Literal["rtsp", "webcam", "uploaded_video"] = "uploaded_video"
    source_uri: str | None = Field(default=None, max_length=2000)


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    station_id: str
    name: str
    source_type: str
    status: str
    last_error: str | None
    last_frame_at: datetime | None


class RuleCreate(BaseModel):
    station_id: str
    name: str = Field(min_length=1, max_length=160)
    rule_type: Literal["color_presence", "motion_stall", "surface_defect", "object_detection"]
    config: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["info", "warning", "high", "critical"] = "warning"
    is_enabled: bool = True

    @field_validator("config")
    @classmethod
    def validate_rule_config(cls, config: dict[str, Any], info):
        rule_type = info.data.get("rule_type")
        if rule_type == "color_presence":
            zone = config.get("zone", [0, 0, 1, 1])
            if not isinstance(zone, list) or len(zone) != 4 or not all(isinstance(v, (int, float)) for v in zone):
                raise ValueError("zone must be [x1,y1,x2,y2] normalized coordinates")
            x1, y1, x2, y2 = zone
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError("zone coordinates must be normalized and increasing")
            hsv_lower = config.get("hsv_lower", [0, 0, 0])
            hsv_upper = config.get("hsv_upper", [179, 255, 255])
            for key, values, maximums in (
                ("hsv_lower", hsv_lower, (179, 255, 255)),
                ("hsv_upper", hsv_upper, (179, 255, 255)),
            ):
                if (
                    not isinstance(values, list)
                    or len(values) != 3
                    or any(type(value) is not int for value in values)
                    or any(value < 0 or value > maximum for value, maximum in zip(values, maximums))
                ):
                    raise ValueError(f"{key} must be three integers within OpenCV HSV ranges")
            if any(lower > upper for lower, upper in zip(hsv_lower, hsv_upper)):
                raise ValueError("hsv_lower values must not exceed hsv_upper values")
            ratio = config.get("min_pixel_ratio", 0.015)
            if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not 0 <= ratio <= 1:
                raise ValueError("min_pixel_ratio must be between 0 and 1")
            consecutive = config.get("min_consecutive", 3)
            if type(consecutive) is not int or not 1 <= consecutive <= 100:
                raise ValueError("min_consecutive must be an integer from 1 to 100")
        elif rule_type == "surface_defect":
            zone = config.get("zone", [0, 0, 1, 1])
            if not isinstance(zone, list) or len(zone) != 4 or not all(isinstance(v, (int, float)) for v in zone):
                raise ValueError("zone must be [x1,y1,x2,y2] normalized coordinates")
            x1, y1, x2, y2 = zone
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError("zone coordinates must be normalized and increasing")
            threshold = config.get("threshold", 24)
            min_area = config.get("min_area", 8)
            if type(threshold) is not int or not 1 <= threshold <= 255:
                raise ValueError("threshold must be an integer from 1 to 255")
            if type(min_area) is not int or not 1 <= min_area <= 100000:
                raise ValueError("min_area must be an integer from 1 to 100000")
            score_threshold = config.get("score_threshold", 0.25)
            if not isinstance(score_threshold, (int, float)) or isinstance(score_threshold, bool) or not 0 <= score_threshold <= 1:
                raise ValueError("score_threshold must be between 0 and 1")
        elif rule_type == "object_detection":
            mode = config.get("mode", "detect")
            if mode not in {"detect", "missing"}:
                raise ValueError("object_detection mode must be detect or missing")
            confidence = config.get("confidence", 0.35)
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 < confidence <= 1:
                raise ValueError("confidence must be between 0 and 1")
            classes = config.get("target_classes", [])
            if not isinstance(classes, list) or any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in classes):
                raise ValueError("target_classes must be a list of non-empty class names")
            if mode == "missing" and not classes:
                raise ValueError("target_classes must contain at least one class when mode is missing")
            model_path = config.get("model_path")
            if model_path is not None and (not isinstance(model_path, str) or len(model_path) > 500):
                raise ValueError("model_path must be a string up to 500 characters")
            required = config.get("min_consecutive", 3)
            if type(required) is not int or not 1 <= required <= 100:
                raise ValueError("min_consecutive must be from 1 to 100")
        elif rule_type == "motion_stall":
            seconds = config.get("inactivity_seconds", 5)
            threshold = config.get("mean_difference_threshold", 2.0)
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0 or seconds > 3600:
                raise ValueError("inactivity_seconds must be in (0, 3600]")
            if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 <= threshold <= 255:
                raise ValueError("mean_difference_threshold must be between 0 and 255")
        return config


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    station_id: str
    name: str
    rule_type: str
    config: dict[str, Any]
    severity: str
    is_enabled: bool
    version: int
    created_at: datetime


class AnalysisCreate(BaseModel):
    station_id: str
    video_id: str
    provider_name: Literal["opencv_rules"] = "opencv_rules"


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    station_id: str
    video_id: str
    status: str
    progress: int
    provider_name: str
    error_message: str | None
    result_summary: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    station_id: str
    video_id: str | None
    job_id: str | None
    rule_id: str | None
    event_type: str
    severity: str
    status: str
    summary: str
    details_json: str
    confidence: float | None
    timestamp_seconds: float
    model_version: str
    rule_version: int | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None
    false_positive_reason: str | None
    created_at: datetime
