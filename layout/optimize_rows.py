import functools, sys
S,D,AMIN,AMAX,STEP=1950,4000,2000,6000,50
def solve(x0,x1,cols,start_wall=True,end_wall=True):
    def col_ok(kind,a,b):
        pin=0
        for c in cols:
            l,r=c-300,c+300
            if r<=a or l>=b: continue
            if kind!='A': continue  # fully/partly in rack ok only if not straddling into aisle -> checked by aisle
            ov_l=max(0,min(r,b)-a) if l<a else 0
            ov_r=max(0,b-max(l,a)) if r>b else 0
            if l>=a and r<=b: return None   # column in middle of aisle
            ov=ov_l or ov_r
            if ov>300 or (b-a-ov)<1700: return None
            pin+=1
        return pin
    @functools.lru_cache(None)
    def f(p,last):  # last: 'R' rack face just placed needing aisle, 'A' aisle placed
        best=None
        if last=='A':
            # end with S against end wall
            if end_wall and p+S==x1: best=(1,0,[('S',p,p+S)])
            if p==x1: best=max(best or (-1,0,[]),(0,0,[]),key=lambda t:(t[0],-t[1]))
            if p+D<=x1:
                r=f(p+D,'R')
                if r: cand=(r[0]+2,r[1],[('D',p,p+D)]+r[2]); best=cand if not best or (cand[0],-cand[1])>(best[0],-best[1]) else best
            return best
        else:
            for w in range(AMIN,AMAX+1,STEP):
                if p+w>x1: break
                pin=col_ok('A',p,p+w)
                if pin is None: continue
                r=f(p+w,'A')
                if r:
                    cand=(r[0],r[1]+pin,[('A',p,p+w)]+r[2])
                    if not best or (cand[0],-cand[1])>(best[0],-best[1]): best=cand
            return best
    res=[]
    if start_wall:
        r=f(x0+S,'R'); 
        if r: res.append((r[0]+1,r[1],[('S',x0,x0+S)]+r[2]))
    r=f(x0,'R')
    if r: res.append(r)
    return max(res,key=lambda t:(t[0],-t[1]))
for name,x0,x1,cols in [('C1',300,47000,[8000,16000,24000,32000,40000]),('C2',49000,95700,[56000,64000,72000,80000,88000])]:
    sc,pin,seq=solve(x0,x1,cols)
    print(name,'sides',sc,'pinches',pin)
    for t,a,b in seq: print(' ',t,a,b,b-a)
