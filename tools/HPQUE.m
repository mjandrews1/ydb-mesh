HPQUE ; min-priority queue over a global (binary heap)
 ;
 ; Schema (same tree as HHEAP, plus tie-break seq):
 ;   ^HPQ(<name>,0)     = n
 ;   ^HPQ(<name>,1,<i>) = priority   (lower = served first)
 ;   ^HPQ(<name>,2,<i>) = payload
 ;   ^HPQ(<name>,3,<i>) = seq        (FIFO among equal priorities)
 ;   ^HPQ(<name>,4)     = next seq
 ;
 ; API:
 ;   D ENQ^HPQUE(name,priority,payload)
 ;   S ok=$$DEQ^HPQUE(name,.priority,.payload)
 ;   S ok=$$TOP^HPQUE(name,.priority,.payload)  ; no remove
 ;   $$QLEN^HPQUE(name)
 ;   D CLEAR^HPQUE(name)
 Q

QLEN(name)
 Q +$G(^HPQ(name,0),0)

; 1 if i should be above j (smaller prio; tie: smaller seq)
BETTER(name,i,j)
 N pi,pj,si,sj
 S pi=+$G(^HPQ(name,1,i)),pj=+$G(^HPQ(name,1,j))
 I pi'=pj Q pi<pj
 S si=+$G(^HPQ(name,3,i)),sj=+$G(^HPQ(name,3,j))
 Q si<sj

SWAP(name,i,j)
 N a,b,c
 S a=^HPQ(name,1,i),b=^HPQ(name,2,i),c=^HPQ(name,3,i)
 S ^HPQ(name,1,i)=^HPQ(name,1,j),^HPQ(name,2,i)=^HPQ(name,2,j),^HPQ(name,3,i)=^HPQ(name,3,j)
 S ^HPQ(name,1,j)=a,^HPQ(name,2,j)=b,^HPQ(name,3,j)=c
 Q

SIFTUP(name,i)
 N p
 F  Q:i'>1  S p=i\2 Q:'$$BETTER(name,i,p)  D SWAP(name,i,p) S i=p
 Q

SIFTDOWN(name,i)
 N n,l,r,m
 S n=+$G(^HPQ(name,0),0)
 F  D  Q:m=i
 . S l=i*2,r=l+1,m=i
 . I l'>n,$$BETTER(name,l,m) S m=l
 . I r'>n,$$BETTER(name,r,m) S m=r
 . I m'=i D SWAP(name,i,m) S i=m
 Q

ENQ(name,priority,payload)
 N n,seq
 S n=+$G(^HPQ(name,0),0)+1
 S seq=+$G(^HPQ(name,4),0)+1
 S ^HPQ(name,1,n)=priority
 S ^HPQ(name,2,n)=payload
 S ^HPQ(name,3,n)=seq
 S ^HPQ(name,0)=n
 S ^HPQ(name,4)=seq
 D SIFTUP(name,n)
 Q

DEQ(name,priority,payload)
 N n
 S n=+$G(^HPQ(name,0),0)
 I n<1 S priority="",payload="" Q 0
 S priority=^HPQ(name,1,1),payload=^HPQ(name,2,1)
 I n=1 D  Q 1
 . K ^HPQ(name,1,1),^HPQ(name,2,1),^HPQ(name,3,1)
 . S ^HPQ(name,0)=0
 S ^HPQ(name,1,1)=^HPQ(name,1,n)
 S ^HPQ(name,2,1)=^HPQ(name,2,n)
 S ^HPQ(name,3,1)=^HPQ(name,3,n)
 K ^HPQ(name,1,n),^HPQ(name,2,n),^HPQ(name,3,n)
 S ^HPQ(name,0)=n-1
 D SIFTDOWN(name,1)
 Q 1

TOP(name,priority,payload)
 I +$G(^HPQ(name,0),0)<1 S priority="",payload="" Q 0
 S priority=^HPQ(name,1,1),payload=^HPQ(name,2,1)
 Q 1

CLEAR(name)
 K ^HPQ(name)
 Q

TEST
 N ok,bad,pr,pl,n
 S bad=0
 D CLEAR^HPQUE("t")
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok W "FAIL deq empty",! S bad=bad+1
 D ENQ^HPQUE("t",3,"three")
 D ENQ^HPQUE("t",1,"one")
 D ENQ^HPQUE("t",2,"two")
 D ENQ^HPQUE("t",1,"one-b")  ; tie prio 1 -> FIFO: one then one-b
 I $$QLEN^HPQUE("t")'=4 W "FAIL len 4",! S bad=bad+1
 S ok=$$TOP^HPQUE("t",.pr,.pl)
 I ok=0!(pr'=1)!(pl'="one") W "FAIL top one",! S bad=bad+1
 I $$QLEN^HPQUE("t")'=4 W "FAIL top mutated",! S bad=bad+1
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok=0!(pl'="one") W "FAIL deq one",! S bad=bad+1
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok=0!(pl'="one-b") W "FAIL deq one-b (FIFO tie)",! S bad=bad+1
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok=0!(pl'="two")!(pr'=2) W "FAIL deq two",! S bad=bad+1
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok=0!(pl'="three")!(pr'=3) W "FAIL deq three",! S bad=bad+1
 S ok=$$DEQ^HPQUE("t",.pr,.pl)
 I ok W "FAIL deq empty after drain",! S bad=bad+1
 W "HPQUE TEST bad=",bad," len=",$$QLEN^HPQUE("t"),!
 Q
