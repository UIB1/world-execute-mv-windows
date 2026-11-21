import bisect, json, math, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAU = math.tau
ESC = '\x1b['
DIM, NORMAL, BRIGHT, WHITE, RED = 0, 1, 2, 3, 4
STYLES = {0:'\x1b[0;38;5;137m',1:'\x1b[0;38;5;215m',2:'\x1b[1;38;5;221m',3:'\x1b[1;38;5;230m',4:'\x1b[1;38;5;203m',5:'\x1b[0;38;5;94m',6:'\x1b[0;38;5;58m'}

FONT = {
'A':['01110','11011','11111','11011','11011'], 'B':['11110','11011','11110','11011','11110'],
'C':['01111','11000','11000','11000','01111'], 'D':['11110','11011','11011','11011','11110'],
'E':['11111','11000','11110','11000','11111'], 'F':['11111','11000','11110','11000','11000'],
'G':['01111','11000','11011','11011','01111'], 'H':['11011','11011','11111','11011','11011'],
'I':['11111','00100','00100','00100','11111'], 'J':['00111','00011','00011','11011','01110'],
'K':['11011','11110','11100','11110','11011'], 'L':['11000','11000','11000','11000','11111'],
'M':['10001','11011','10101','10001','10001'], 'N':['11001','11101','11111','10111','10011'],
'O':['01110','11011','11011','11011','01110'], 'P':['11110','11011','11110','11000','11000'],
'Q':['01110','11011','11011','01110','00011'], 'R':['11110','11011','11110','11101','11011'],
'S':['01111','11000','01110','00011','11110'], 'T':['11111','00100','00100','00100','00100'],
'U':['11011','11011','11011','11011','01110'], 'V':['11011','11011','11011','01110','00100'],
'W':['10001','10001','10101','11011','10001'], 'X':['11011','01110','00100','01110','11011'],
'Y':['11011','11011','01110','00100','00100'], 'Z':['11111','00011','00110','01100','11111'],
'0':['01110','11011','11011','11011','01110'], '1':['00100','01100','00100','00100','01110'],
'2':['11110','00011','01110','11000','11111'], '3':['11110','00011','01110','00011','11110'],
'4':['11011','11011','11111','00011','00011'], '5':['11111','11000','11110','00011','11110'],
'6':['01111','11000','11110','11011','01110'], '7':['11111','00011','00110','01100','01100'],
'8':['01110','11011','01110','11011','01110'], '9':['01110','11011','01111','00011','11110'],
';':['00000','00100','00000','00100','01000'], '.':['00000','00000','00000','00000','00100'],
'(':['00010','00100','00100','00100','00010'], ')':['01000','00100','00100','00100','01000'],
'-':['00000','00000','11111','00000','00000'], ' ':['00000']*5,
}

def cw(ch):
    if unicodedata.combining(ch): return 0
    return 2 if unicodedata.east_asian_width(ch) in ('W','F') else 1

def width(s): return sum(cw(c) for c in s)

def crop(s, n):
    out=''; used=0
    for ch in s:
        k=cw(ch)
        if used+k>n: break
        out+=ch; used+=k
    return out

def wrap(s, n):
    if width(s)<=n: return [s]
    parts=[]
    while s:
        line=crop(s,n)
        if len(line)<len(s) and ' ' in line and all(ord(c)<128 for c in s):
            line=line.rsplit(' ',1)[0]
        parts.append(line); s=s[len(line):].lstrip()
    return parts

class Canvas:
    def __init__(self,w,h):
        self.w=w; self.h=h
        self.clip=None
        self.cells=[[(' ',DIM) for _ in range(w)] for _ in range(h)]
    def put(self,x,y,s,style=NORMAL):
        x=int(x); y=int(y)
        if not 0<=y<self.h: return
        if self.clip and not self.clip[0]<=y<=self.clip[1]:return
        for ch in str(s):
            k=cw(ch)
            if k==0: continue
            if x>=0 and x+k<=self.w:
                self.cells[y][x]=(ch,style)
                if k==2: self.cells[y][x+1]=('',style)
            x+=k
    def center(self,y,s,style=NORMAL): self.put((self.w-width(s))//2,y,s,style)
    def line(self,x0,y0,x1,y1,ch='.',style=DIM):
        steps=max(1,int(max(abs(x1-x0),abs(y1-y0))*1.5))
        for i in range(steps+1):
            u=i/steps; self.put(round(x0+(x1-x0)*u),round(y0+(y1-y0)*u),ch,style)
    def box(self,x,y,w,h,style=DIM):
        if w<2 or h<2:return
        self.put(x,y,'+'+'-'*(w-2)+'+',style)
        self.put(x,y+h-1,'+'+'-'*(w-2)+'+',style)
        for yy in range(y+1,y+h-1):
            self.put(x,yy,'|',style); self.put(x+w-1,yy,'|',style)
    def big(self,y,text,style=BRIGHT):
        text=text.upper(); total=len(text)*6-1
        if total>self.w-6:
            self.center(y+2,text,style); return
        left=(self.w-total)//2
        for i,ch in enumerate(text):
            for dy,row in enumerate(FONT.get(ch,FONT[' '])):
                for dx,p in enumerate(row):
                    if p=='1':self.put(left+i*6+dx,y+dy,'#',style)
    def ansi(self):
        out=['\x1b[H']; last=None
        for y,row in enumerate(self.cells):
            out.append(f'\x1b[{y+1};1H')
            for ch,style in row:
                if not ch: continue
                if style!=last:out.append(STYLES[style]);last=style
                out.append(ch)
        return ''.join(out)+'\x1b[0m'
    def plain(self): return '\n'.join(''.join(ch for ch,_ in r) for r in self.cells)

CHAPTERS=[(0,'01 / CREATION','创建'),(29.709,'02 / DEVOTION','献出自我'),
          (110.9,'03 / ISOLATION','离开'),(125.708,'04 / EXECUTION','失控'),
          (177.246,'05 / LOVE','困于爱')]

class Film:
    def __init__(self):
        self.lyrics=json.loads((ROOT/'lyrics.json').read_text(encoding='utf-8'))
        self.times=[x['time'] for x in self.lyrics]
        self.spectrum=json.loads((ROOT/'spectrum.json').read_text(encoding='utf-8'))
        self.config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    def cue(self,t):
        idx=bisect.bisect_right(self.times,t)-1
        e=self.lyrics[idx] if idx>=0 else None
        return e if e and t<e['end'] else None
    def energy(self,t):
        a=self.spectrum['frames']
        return a[min(len(a)-1,max(0,int(t*self.spectrum['fps'])))]
    def render(self,t,w,h,paused=False,offset=0,help_on=False,ready=False):
        c=Canvas(w,h)
        if w<64 or h<24:
            c.center(h//2-2,'WORLD.EXECUTE(ME);',BRIGHT)
            c.center(h//2,'请放大窗口，或缩小终端字号',WHITE)
            c.center(h//2+2,f'{w} x {h} / minimum 64 x 24',NORMAL)
            c.center(h//2+4,'SPACE pause  Q quit',DIM)
            return c
        if 15.8<=t<29.709 and not ready:
            from scenes import title_takeover
            source=self.render(15.799,w,h,paused,offset,False,False) if t<18.1 else None
            title_takeover(c,t,FONT,source)
            if help_on:self.help(c,offset)
            return c
        end=self.config['duration']; e=self.cue(t+offset)
        act=max(x for x in CHAPTERS if x[0]<=max(0,t))
        c.put(2,0,'WORLD.EXECUTE(ME);',BRIGHT)
        state='READY' if ready else ('PAUSED' if paused else 'RUNNING')
        clock=f'{int(t)//60:02}:{int(t)%60:02}.{int(t*10)%10} / 03:32  {state}'
        c.put(w-width(clock)-2,0,clock,DIM)
        c.put(2,1,'-'*(w-4),DIM)
        c.put(2,2,act[1],NORMAL)
        top=4; bottom=h-8; cy=(top+bottom)/2; cx=w/2
        sh=max(6,bottom-top+1)
        spec=self.energy(t)
        pulse=sum(spec[:10])/10
        c.clip=(top,bottom)
        from scenes import draw_scene, phosphor
        draw_scene(c,t,top,bottom,pulse,e)
        phosphor(c,t,top,bottom)
        c.clip=None
        # Spectrum is measured from the supplied song, sampled on the audio clock.
        sy=h-6; cols=min(80,w-8); start=(w-cols)//2
        for i in range(cols):
            amp=spec[int(i*48/cols)]; level=max(0,round(amp*3))
            c.put(start+i,sy,'._:=|'[min(4,round(amp*4))],DIM)
        if ready:
            c.center(h-5,'MILI  /  world.execute(me);',WHITE)
            c.center(h-3,'[ SPACE / ENTER TO START ]',BRIGHT)
        elif e:
            ens=wrap(e['en'],w-8); zhs=wrap(e['zh'],w-8)
            # Two reserved lines per language prevent changes in caption position.
            for i,line in enumerate(ens[:2]):c.center(h-5+i,line,WHITE)
            for i,line in enumerate(zhs[:2]):c.center(h-3+i,line,BRIGHT)
        elif t>208:
            c.center(h-5,'PROCESS ENDED. THE LOOP REMAINS.',WHITE)
        else:
            c.center(h-5,'[ instrumental ]',DIM)
            c.center(h-3,'[ 间奏 ]',DIM)
        hint='SPACE play/pause   <- -> 5s   R restart   Q quit   H help'
        c.center(h-1,crop(hint,w-4),DIM)
        if ready:self.slate(c,top,bottom)
        if help_on:self.help(c,offset)
        return c
    def slate(self,c,top,bottom):
        for y in range(top,bottom+1):c.put(0,y,' '*c.w,DIM)
        cy=int((top+bottom)/2)
        c.center(top+1,'A TERMINAL MUSIC VIDEO',DIM)
        c.big(max(top+2,cy-4),'EXECUTE(ME);',BRIGHT)
        c.center(cy+3,'M I L I',WHITE)
        c.center(min(bottom,cy+6),'[ SPACE / ENTER TO START ]',BRIGHT)
    def help(self,c,offset):
        lines=['CONTROLS / 操作','SPACE / ENTER   播放或暂停','LEFT / RIGHT    后退或前进 5 秒',
               'R               从头播放','1 2 3 4 5       跳转五个章节','[ / ]           字幕提前 / 延后 0.1 秒',
               ', / .           上一句 / 下一句',
               '+ / -           音量','Q / ESC         退出','H               关闭帮助',f'字幕偏移 {offset:+.1f}s']
        w=min(c.w-4,58);x=(c.w-w)//2;y=(c.h-len(lines)-3)//2
        for yy in range(y,y+len(lines)+3):c.put(x,yy,' '*w,NORMAL)
        c.box(x,y,w,len(lines)+3,BRIGHT)
        for i,s in enumerate(lines):c.put(x+3,y+2+i,s,WHITE if i==0 else NORMAL)
