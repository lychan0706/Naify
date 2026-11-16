// ============================================================
// Naify Chrome Extension - Content Script
//
// 역할:
// 1. 웹페이지에서 Naify 이미지 검색
// 2. 새로운 이미지가 등장하면 자동으로 감지
// 3. 이미 처리한 이미지의 중복 감지 방지
// ============================================================


// 이미 처리한 이미지 요소를 기억하는 저장소
// WeakSet은 HTML 요소가 제거되면 메모리 정리를 방해하지 않음
const processedImages = new WeakSet();


// ------------------------------------------------------------
// Naify 이미지 검색
// ------------------------------------------------------------
function findNaifyImages() {

    // 뤼튼 크랙의 Markdown 영역에 포함된 모든 이미지 검색
    const images = document.querySelectorAll(".wrtn-markdown img");

    images.forEach((image) => {

        // 이미 처리한 이미지라면 건너뛰기
        if (processedImages.has(image)) {
            return;
        }

        // 이미지의 원본 URL 가져오기
        const url = image.getAttribute("src");

        // Naify 이미지인지 확인
        if (url?.startsWith("http://127.0.0.1:8000/get_image?")) {

            // 처리한 이미지로 등록하여 중복 감지 방지
            processedImages.add(image);

            // 개발자 도구에 감지 결과 출력
            console.log("[Naify] Image detected:", url);
        }
    });
}


// ------------------------------------------------------------
// 웹페이지 변경 감시
// ------------------------------------------------------------

// HTML 요소가 추가되거나 제거될 때 호출되는 감시자
const observer = new MutationObserver(() => {

    // 변경이 발생하면 Naify 이미지 다시 검색
    findNaifyImages();
});


// 웹페이지 전체의 HTML 요소 추가 및 제거 감시
observer.observe(document.body, {

    // 자식 요소가 추가되거나 제거되는지 감시
    childList: true,

    // 하위 요소 전체까지 감시
    subtree: true
});


// ------------------------------------------------------------
// 초기 실행
// ------------------------------------------------------------

// Content Script가 정상적으로 실행되었는지 확인
console.log("[Naify] Content script initialized.");

// 이미 웹페이지에 존재하는 이미지 검색
findNaifyImages();