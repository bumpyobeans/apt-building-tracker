"""카카오 나에게 보내기 클라이언트"""
import requests


TOKEN_URL = 'https://kauth.kakao.com/oauth/token'
SEND_URL = 'https://kapi.kakao.com/v2/api/talk/memo/default/send'


def refresh_access_token(app_key: str, refresh_token: str) -> tuple[str, str | None]:
    """리프레시 토큰으로 새 액세스 토큰 발급. 새 리프레시 토큰이 있으면 함께 반환."""
    resp = requests.post(TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'client_id': app_key,
        'refresh_token': refresh_token,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    access_token = data['access_token']
    new_refresh = data.get('refresh_token')  # 갱신 시에만 포함됨
    return access_token, new_refresh


def send_message(app_key: str, refresh_token: str, text: str, notion_url: str = '') -> str | None:
    """카카오 나에게 보내기. 새 리프레시 토큰이 발급되면 반환."""
    access_token, new_refresh = refresh_access_token(app_key, refresh_token)

    link_text = '📋 Notion에서 전체 보기' if notion_url else ''
    template = {
        'object_type': 'text',
        'text': text[:200],  # 카카오 텍스트 최대 200자
        'link': {
            'web_url': notion_url or 'https://notion.so',
            'mobile_web_url': notion_url or 'https://notion.so',
        },
    }
    if notion_url:
        template['button_title'] = link_text

    resp = requests.post(
        SEND_URL,
        headers={'Authorization': f'Bearer {access_token}'},
        data={'template_object': str(template).replace("'", '"')},
        timeout=10,
    )
    resp.raise_for_status()

    if new_refresh:
        print(f'[카카오] 리프레시 토큰 갱신됨. .env의 KAKAO_REFRESH_TOKEN을 아래 값으로 업데이트하세요:')
        print(f'  {new_refresh}')

    return new_refresh
