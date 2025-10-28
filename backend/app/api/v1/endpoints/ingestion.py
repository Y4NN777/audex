from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/batches", summary="Upload a batch of audit files")
async def create_batch(files: list[UploadFile]) -> dict[str, int]:
    """Placeholder endpoint returning number of received files."""
    return {"received": len(files)}
