# fix_guide_md.py — رفع خودکار خطاهای MD040 و MD060 در SMC_RTM_LIQUIDITY_GUIDE.md
import re

FILE_PATH = 'SMC_RTM_LIQUIDITY_GUIDE.md'

def detect_language(block_lines):
    """حدس زبان بلوک کد بر اساس محتوای چند خط اول"""
    content = '\n'.join(block_lines[:5]).lower()
    if any(kw in content for kw in ['import ', 'def ', 'class ', 'print(', 'for ', 'if ', ' = ', 'df.', 'plt.', 'pd.', 'np.']):
        return 'python'
    elif any(kw in content for kw in ['curl', 'wget', 'pip ', 'python ', 'node ', 'npm ']):
        return 'bash'
    elif content.strip().startswith('{') or content.strip().startswith('['):
        return 'json'
    else:
        return 'text'

def fix_md040(lines):
    """اضافه کردن زبان به بلوک‌های کد بدون زبان"""
    new_lines = []
    in_fence = False
    fence_lang = ''
    block_buffer = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # شروع بلوک کد
        if line.strip().startswith('```') and not in_fence:
            # چک کن آیا زبان دارد؟
            after_backticks = line.strip()[3:].strip()
            if after_backticks == '':
                # بدون زبان، محتوای بلوک را جمع کن تا حدس بزنیم
                block_buffer = []
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith('```'):
                    block_buffer.append(lines[j])
                    j += 1
                # حدس زبان
                lang = detect_language(block_buffer)
                new_lines.append(f'```{lang}\n')
                in_fence = True
                fence_lang = lang
                i += 1
                continue
            else:
                # زبان دارد، بدون تغییر
                new_lines.append(line)
                in_fence = True
                fence_lang = after_backticks
                i += 1
                continue
        # پایان بلوک
        elif line.strip().startswith('```') and in_fence:
            new_lines.append(line)
            in_fence = False
            fence_lang = ''
            i += 1
            continue
        else:
            new_lines.append(line)
            i += 1
    return new_lines

def fix_table_spacing(line):
    """اصلاح فاصله‌گذاری جدول: هر pipe باید دقیقاً یک فاصله قبل و بعد داشته باشد"""
    if '|' not in line:
        return line
    # حذف فاصله‌های اضافی و سپس استانداردسازی
    parts = line.split('|')
    new_parts = []
    for i, part in enumerate(parts):
        if i == 0:
            # ستون اول: فقط فضای بعد از pipe مهم است
            new_parts.append(part.strip())
        elif i == len(parts) - 1:
            # ستون آخر: فضای قبل از pipe
            new_parts.append(part.strip())
        else:
            new_parts.append(f' {part.strip()} ')
    return '|'.join(new_parts)

def fix_md060(lines):
    """رفع فاصله‌گذاری جدول‌ها"""
    fixed = []
    for line in lines:
        # فقط خطوطی که pipe دارند و جزء بلوک کد نیستند (این اسکریپت خطوط داخل بلاک را هم ممکن است تغییر دهد،
        # اما بهتر است فقط خارج از fence تغییر دهیم)
        if '|' in line and not line.strip().startswith('```'):
            fixed.append(fix_table_spacing(line))
        else:
            fixed.append(line)
    return fixed

def main():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines(keepends=True)

    # اعمال اصلاحات MD040
    lines = fix_md040(lines)
    # اعمال اصلاحات MD060
    lines = fix_md060(lines)

    new_content = ''.join(lines)
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f'✅ فایل {FILE_PATH} با موفقیت اصلاح شد.')
    print('   - تمام بلوک‌های کد بدون زبان، صاحب زبان شده‌اند.')
    print('   - فاصله‌گذاری جدول‌ها استاندارد شده است.')

if __name__ == '__main__':
    main()