# Dark-mode palette used for the v19.6 dark boards (design chat, 2026-11-06). Reference only: the app gets its dark tokens from the task file, Part D.
import re, sys
P = 'docs/design/v19.6/reference/'   # reads <Board>.dc.html, writes <Board>Dark.dc.html next to it
BG = {'#F5F3EF': '#10151E', '#FFFFFF': '#1A2231', '#1C2B45': '#31456B', '#F2F0EB': '#232C3C', '#E9F5EE': '#1C3328', '#FBF4E1': '#362E1D',
      '#EAF1FB': '#1D2B43', '#F1EDF9': '#2A2541', '#E6F4F4': '#1B3535', '#EDF4EF': '#1C3328', '#DCEFE3': '#24493A', '#F6EACB': '#4A3E22',
      '#DCE7F7': '#26395A', '#E6E0F5': '#3A3160', '#D5EDED': '#21474A', '#E3E7EE': '#2B3548', '#ECE8E1': '#232C3C', '#E8E4DE': '#2A3446',
      '#F0EDE8': '#2A3446', '#E3DED6': '#2E384A', '#D9D4CC': '#3A4558', '#EEF0F4': '#232C3C', '#CDEBD9': '#2E5A44', '#FFE2A8': '#5A4718',
      '#E3E6EB': '#2E384A', '#F6E3B4': '#4A3E22', '#EAEDF2': '#2A3446', '#E9E5DF': '#2A3446', '#F5F3EF80': '#10151E80'}
TX = {'#1C2B45': '#E8ECF2', '#3D4B63': '#C3CCD9', '#5B6576': '#9BA6B7', '#6B7280': '#8E99AA', '#9AA3B2': '#6F7B8E', '#B4BAC5': '#5E697B',
      '#E3E7EE': '#C3CCD9', '#CBD3DF': '#AEB9C9', '#D6303F': '#FF6B75', '#2563EB': '#7AA2FF', '#8A5A00': '#F1C25B', '#1F7A4D': '#6FD39F',
      '#FFFFFF': '#FFFFFF', '#C59A2E': '#E3BA55', '#4E9A72': '#7CC79F', '#6E93CF': '#93B4EA', '#8C78C6': '#B3A2EC', '#3E9A9A': '#6CC3C3'}
LN = {'#F0EDE8': '#2A3446', '#ECE8E1': '#2A3446', '#E8E4DE': '#2A3446', '#E3DED6': '#334055', '#E0DCD5': '#334055', '#D9D4CC': '#3A4558',
      '#C9C2B8': '#465267', '#1C2B45': '#AEB9C9', '#E3E6EB': '#334055'}
ICON = {'#1C2B45': '#E8ECF2', '#5B6576': '#9BA6B7', '#D6303F': '#FF6B75', '#2563EB': '#7AA2FF', '#9AA3B2': '#6F7B8E', '#D9D4CC': '#3A4558',
        '#E3DED6': '#334055', '#EEF0F4': '#2B3548', '#1F7A4D': '#6FD39F'}
def mp(table, c):
    return table.get(c.upper(), c)
def dark(html):
    body_start = html.find('<body')
    head, body = html[:body_start], html[body_start:]
    # backgrounds (incl. gradients)
    def bgrep(m):
        val = re.sub(r'#[0-9A-Fa-f]{6}', lambda x: mp(BG, x.group(0)), m.group(2))
        val = val.replace('rgba(255,255,255,0)', 'rgba(26,34,49,0)')
        return m.group(1) + val
    body = re.sub(r'(background(?:-color)?:\s*)([^;"]+)', bgrep, body)
    body = re.sub(r'((?<![-\w])color:\s*)(#[0-9A-Fa-f]{6})', lambda m: m.group(1) + mp(TX, m.group(2)), body)
    body = re.sub(r'(box-shadow:\s*[^;"]*?)(#[0-9A-Fa-f]{6})', lambda m: m.group(1) + mp(LN, m.group(2)), body)
    body = re.sub(r'(border(?:-top|-bottom|-left|-right)?:\s*[^;"]*?)(#[0-9A-Fa-f]{6})', lambda m: m.group(1) + mp(LN, m.group(2)), body)
    body = re.sub(r'((?:fill|stroke)=")(#[0-9A-Fa-f]{6})', lambda m: m.group(1) + mp(ICON, m.group(2)), body)
    body = re.sub(r'(<text[^>]*?fill=")(#[0-9A-Fa-f]{6})', lambda m: m.group(1) + mp(TX, m.group(2)), body)
    # 뱁이 logo mark (navy line art) sits on a light round chip in dark mode; the art itself is untouched
    body = body.replace('alt="" style="width: 28px; height: 28px; display: block">',
                        'alt="" style="width: 28px; height: 28px; display: block; background: #F5F3EF; border-radius: 50%; padding: 2px; box-sizing: border-box">')
    body = body.replace('예시 데이터</span>', '예시 데이터 · 어두운 화면</span>', 1)
    return head + body
if __name__ == '__main__':
    for src, dst in [(a, a + 'Dark') for a in sys.argv[1:]]:
        t = open(P + src + '.dc.html', encoding='utf-8').read()
        open(P + dst + '.dc.html', 'w', encoding='utf-8').write(dark(t))
    print('dark ok')
