"""Static geography and frame listing."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_repository
from app.data.repository import Repository
from app.domain.image import ImageMeta
from app.domain.scene import Scene

router = APIRouter(tags=["scene"])


@router.get("/scene", response_model=Scene)
def get_scene(repo: Annotated[Repository, Depends(get_repository)]) -> Scene:
    """Base and zones."""
    return repo.scene


@router.get("/images", response_model=list[ImageMeta])
def list_images(repo: Annotated[Repository, Depends(get_repository)]) -> list[ImageMeta]:
    """All frames sorted by capture time."""
    return repo.list_images()


@router.get("/images/{image_id}/file", response_class=FileResponse)
def get_image_file(
    image_id: str, repo: Annotated[Repository, Depends(get_repository)]
) -> FileResponse:
    """Raw frame image (no filesystem paths leak to the client)."""
    return FileResponse(repo.image_path(image_id))
