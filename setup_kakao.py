"""카카오 최초 인증 설정 스크립트 — 처음 한 번만 실행"""
import os
import webbrowser
import requests
from dotenv import load_dotenv

load_dotenv('.env')

APP_KEY = os.environ.get('KAKAO_APP_KEY', '')
REDIRECT_URI = 'https://example.com/oauth'  # 카카오 앱 설정에도 동일하게 등록 필요

AUTH_URL = (
    f'https://kauth.kakao.com/oauth/authorize'
    f'?client_id={APP_KEY}'
    f'&redirect_uri={REDIRECT_URI}'
    f'&response_type=code'
    f'&scope=talk_message'
)


def main():
    if not APP_KEY:
        print('❌ .env 파일에 KAKAO_APP_KEY를 먼저 설정하세요.')
        return

    print('=== 카카오 인증 설정 ===')
    print()
    print('1단계: 아래 URL을 브라우저에서 열어 카카오 로그인 후 동의합니다.')
    print(f'\n  {AUTH_URL}\n')
    webbrowser.open(AUTH_URL)

    print('2단계: 로그인 완료 후 브라우저 주소창에서 code= 뒤의 값을 복사하세요.')
    print('  예) https://example.com/oauth?code=ABCDEF1234  →  ABCDEF1234\n')
    code = input('code 값 입력: ').strip()

    resp = requests.post('https://kauth.kakao.com/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': APP_KEY,
        'redirect_uri': REDIRECT_URI,
        'code': code,
    })
    resp.raise_for_status()
    data = resp.json()

    access_token = data.get('access_token', '')
    refresh_token = data.get('refresh_token', '')

    print('\n✅ 토큰 발급 성공!')
    print(f'  액세스 토큰:   {access_token[:20]}...')
    print(f'  리프레시 토큰: {refresh_token[:20]}...')
    print()
    print('.env 파일의 KAKAO_REFRESH_TOKEN에 아래 값을 붙여넣으세요:')
    print(f'\n  {refresh_token}\n')

    # .env 자동 업데이트 여부 확인
    answer = input('.env 파일을 자동으로 업데이트할까요? [y/N] ').strip().lower()
    if answer == 'y':
        _update_env('.env', 'KAKAO_REFRESH_TOKEN', refresh_token)
        print('✅ .env 업데이트 완료')


def _update_env(path: str, key: str, value: str) -> None:
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}\n'
                updated = True
                break
        if not updated:
            lines.append(f'{key}={value}\n')
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except FileNotFoundError:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')


if __name__ == '__main__':
    main()
