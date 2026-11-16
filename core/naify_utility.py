import io
from datetime import datetime
import zipfile

def print_log(image_id:str = "SERVER", content: str = "") -> None:
    """
    현재 시각을 HH:MM:SS 형식으로 표시하고 로그를 출력한다.
    """
    
    now = datetime.now()
    timestamp = now.strftime("%H:%M:%S.%f")[:-3]

    print(f"[{timestamp}] {image_id[:6]} : {content}")


def extract_image_from_zip(zip_data: bytes) -> bytes:
    """
    ZIP 바이너리 데이터에서 첫 번째 이미지 파일을 추출한다.

    Args:
        zip_data: ZIP 파일의 바이너리 데이터.

    Returns:
        bytes: 압축 해제된 이미지 데이터.
    """

    zip_file = io.BytesIO(zip_data)
    with zipfile.ZipFile(zip_file, "r") as response_zip:
        image_bytes = response_zip.read(response_zip.namelist()[0])
    return image_bytes