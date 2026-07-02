"""
database.py - Kết nối MongoDB và CRUD operations
Traffic Violation Detection System v4.0
Collections: detections, violations, analysis_jobs
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import DESCENDING
from bson import ObjectId

from .config import MONGO_URI, MONGO_DB
from .models import DetectionCreate, ViolationCreate

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo() -> None:
    global _client, _db
    try:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[MONGO_DB]
        await _client.admin.command("ping")
        logger.info(f"✅ Kết nối MongoDB thành công: {MONGO_URI}/{MONGO_DB}")
        await _ensure_indexes()
    except Exception as e:
        logger.error(f"❌ Không thể kết nối MongoDB: {e}")


async def close_mongo_connection() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_db() -> Optional[AsyncIOMotorDatabase]:
    return _db


async def _ensure_indexes() -> None:
    if _db is None:
        return

    # Detections indexes
    detections = _db["detections"]
    await detections.create_index([("created_at", DESCENDING)])
    await detections.create_index([("vehicle_class", 1)])
    await detections.create_index([("category", 1)])
    await detections.create_index([("camera_id", 1)])

    # Violations indexes
    violations = _db["violations"]
    await violations.create_index([("created_at", DESCENDING)])
    await violations.create_index([("violation_type", 1)])
    await violations.create_index([("plate_text", 1)])
    await violations.create_index([("camera_id", 1)])

    # Analysis jobs indexes
    jobs = _db["analysis_jobs"]
    await jobs.create_index([("status", 1)])
    await jobs.create_index([("created_at", DESCENDING)])


# ---------------------------------------------------------------------------
# CRUD – Detections (vehicles)
# ---------------------------------------------------------------------------

async def create_detection(data: DetectionCreate) -> Optional[str]:
    if _db is None:
        return None
    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    result = await _db["detections"].insert_one(doc)
    return str(result.inserted_id)


async def get_detections(
    skip: int = 0,
    limit: int = 50,
    vehicle_class: Optional[str] = None,
    category: Optional[str] = None,
    camera_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
) -> List[dict]:
    if _db is None:
        return []
    query: dict = {}
    if vehicle_class:
        query["vehicle_class"] = vehicle_class
    if category:
        query["category"] = category
    if camera_id:
        query["camera_id"] = camera_id
    if source_file:
        query["source_file"] = source_file
    if source_type:
        query["source_type"] = source_type
    if start_time or end_time:
        query["created_at"] = {}
        if start_time:
            query["created_at"]["$gte"] = start_time
        if end_time:
            query["created_at"]["$lte"] = end_time

    cursor = (
        _db["detections"]
        .find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


async def count_detections(
    vehicle_class: Optional[str] = None,
    category: Optional[str] = None,
    camera_id: Optional[str] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
) -> int:
    if _db is None:
        return 0
    query: dict = {}
    if vehicle_class:
        query["vehicle_class"] = vehicle_class
    if category:
        query["category"] = category
    if camera_id:
        query["camera_id"] = camera_id
    if source_file:
        query["source_file"] = source_file
    if source_type:
        query["source_type"] = source_type
    return await _db["detections"].count_documents(query)


async def delete_detection(detection_id: str) -> bool:
    if _db is None:
        return False
    result = await _db["detections"].delete_one({"_id": ObjectId(detection_id)})
    return result.deleted_count > 0


async def get_stats(hours: int = 24) -> dict:
    """Thống kê phân loại xe theo class và category"""
    if _db is None:
        return {}
    since = datetime.utcnow() - timedelta(hours=hours)

    # Aggregation by class
    pipeline_class = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$vehicle_class", "count": {"$sum": 1}}},
    ]
    cursor_class = _db["detections"].aggregate(pipeline_class)
    result_class = await cursor_class.to_list(length=100)
    by_class = {item["_id"]: item["count"] for item in result_class if item["_id"]}

    # Aggregation by category
    pipeline_cat = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    cursor_cat = _db["detections"].aggregate(pipeline_cat)
    result_cat = await cursor_cat.to_list(length=100)
    by_category = {item["_id"]: item["count"] for item in result_cat if item["_id"]}

    total = sum(by_class.values())
    return {
        "period_hours": hours,
        "period_start": since.isoformat(),
        "period_end": datetime.utcnow().isoformat(),
        "total_detections": total,
        "by_class": by_class,
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# CRUD – Violations (vi phạm giao thông)
# ---------------------------------------------------------------------------

async def create_violation(data: ViolationCreate) -> Optional[str]:
    if _db is None:
        return None
    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    result = await _db["violations"].insert_one(doc)
    return str(result.inserted_id)


async def get_violations(
    skip: int = 0,
    limit: int = 50,
    violation_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    plate_text: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
) -> List[dict]:
    if _db is None:
        return []
    query: dict = {}
    if violation_type:
        query["violation_type"] = violation_type
    if camera_id:
        query["camera_id"] = camera_id
    if source_file:
        query["source_file"] = source_file
    if source_type:
        query["source_type"] = source_type
    if plate_text:
        # Tìm kiếm biển số chứa chuỗi con (case-insensitive)
        query["plate_text"] = {"$regex": plate_text, "$options": "i"}
    if start_time or end_time:
        query["created_at"] = {}
        if start_time:
            query["created_at"]["$gte"] = start_time
        if end_time:
            query["created_at"]["$lte"] = end_time

    cursor = (
        _db["violations"]
        .find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


async def count_violations(
    violation_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
) -> int:
    if _db is None:
        return 0
    query: dict = {}
    if violation_type:
        query["violation_type"] = violation_type
    if camera_id:
        query["camera_id"] = camera_id
    if source_file:
        query["source_file"] = source_file
    if source_type:
        query["source_type"] = source_type
    return await _db["violations"].count_documents(query)


async def delete_violation(violation_id: str) -> bool:
    if _db is None:
        return False
    result = await _db["violations"].delete_one({"_id": ObjectId(violation_id)})
    return result.deleted_count > 0


async def get_violation_stats(hours: int = 24) -> dict:
    """Thống kê vi phạm theo loại"""
    if _db is None:
        return {}
    since = datetime.utcnow() - timedelta(hours=hours)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$violation_type", "count": {"$sum": 1}}},
    ]
    cursor = _db["violations"].aggregate(pipeline)
    results = await cursor.to_list(length=100)
    by_type = {item["_id"]: item["count"] for item in results if item["_id"]}

    total = sum(by_type.values())
    return {
        "period_hours": hours,
        "period_start": since.isoformat(),
        "period_end": datetime.utcnow().isoformat(),
        "total_violations": total,
        "by_type": by_type,
    }


# ---------------------------------------------------------------------------
# CRUD – Analysis Jobs
# ---------------------------------------------------------------------------

async def create_analysis_job(filename: str, file_size: int,
                              duration_sec: float = 0,
                              total_frames: int = 0,
                              filepath: Optional[str] = None) -> Optional[str]:
    if _db is None:
        return None
    doc = {
        "filename": filename,
        "file_size": file_size,
        "duration_sec": duration_sec,
        "total_frames": total_frames,
        "filepath": filepath,
        "status": "pending",
        "progress": 0.0,
        "processed_frames": 0,
        "vehicles_detected": 0,
        "violations_detected": 0,
        "plates_detected": 0,
        "counts_by_class": {},
        "counts_by_category": {},
        "counts_by_violation": {},
        "error_message": None,
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
    }
    result = await _db["analysis_jobs"].insert_one(doc)
    return str(result.inserted_id)


async def update_analysis_job(job_id: str, **kwargs) -> bool:
    if _db is None:
        return False
    result = await _db["analysis_jobs"].update_one(
        {"_id": ObjectId(job_id)},
        {"$set": kwargs}
    )
    return result.modified_count > 0


async def get_analysis_job(job_id: str) -> Optional[dict]:
    if _db is None:
        return None
    doc = await _db["analysis_jobs"].find_one({"_id": ObjectId(job_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
