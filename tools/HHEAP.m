HHEAP ; binary min-heap over a global (1-based complete tree)
 ;
 ; Schema:
 ;   ^HHEAP(<name>,0)     = n (heap size)
 ;   ^HHEAP(<name>,1,<i>) = key  (min-heap: parent key <= child key)
 ;   ^HHEAP(<name>,2,<i>) = payload
 ;
 ; API:
 ;   D PUSH^HHEAP(name,key,payload)
 ;   S ok=$$POP^HHEAP(name,.key,.payload)  ; extract-min
 ;   S ok=$$PEEK^HHEAP(name,.key,.payload) ; no pop
 ;   $$HHEAPN^HHEAP(name)
 ;   D CLEAR^HHEAP(name)
 Q

HHEAPN(name)
 Q +$G(^HHEAP(name,0),0)

; compare keys: 1 if a<b (numeric first, else string collation)
LT(a,b)
 I a?1.N,b?1.N Q (+a)<(+b)
 Q (b]a)

SWAP(name,i,j)
 N kp,pl
 S kp=^HHEAP(name,1,i),pl=^HHEAP(name,2,i)
 S ^HHEAP(name,1,i)=^HHEAP(name,1,j),^HHEAP(name,2,i)=^HHEAP(name,2,j)
 S ^HHEAP(name,1,j)=kp,^HHEAP(name,2,j)=pl
 Q

SIFTUP(name,i)
 N p
 F  Q:i'>1  S p=i\2 Q:'$$LT(^HHEAP(name,1,i),^HHEAP(name,1,p))  D SWAP(name,i,p) S i=p
 Q

SIFTDOWN(name,i)
 N n,l,r,m
 S n=+$G(^HHEAP(name,0),0)
 F  D  Q:m=i
 . S l=i*2,r=l+1,m=i
 . I l'>n,$$LT(^HHEAP(name,1,l),^HHEAP(name,1,m)) S m=l
 . I r'>n,$$LT(^HHEAP(name,1,r),^HHEAP(name,1,m)) S m=r
 . I m'=i D SWAP(name,i,m) S i=m
 Q

PUSH(name,key,payload)
 N n
 S n=+$G(^HHEAP(name,0),0)+1
 S ^HHEAP(name,1,n)=key
 S ^HHEAP(name,2,n)=payload
 S ^HHEAP(name,0)=n
 D SIFTUP(name,n)
 Q

POP(name,key,payload)
 N n
 S n=+$G(^HHEAP(name,0),0)
 I n<1 S key="",payload="" Q 0
 S key=^HHEAP(name,1,1),payload=^HHEAP(name,2,1)
 I n=1 K ^HHEAP(name,1,1),^HHEAP(name,2,1) S ^HHEAP(name,0)=0 Q 1
 S ^HHEAP(name,1,1)=^HHEAP(name,1,n),^HHEAP(name,2,1)=^HHEAP(name,2,n)
 K ^HHEAP(name,1,n),^HHEAP(name,2,n)
 S ^HHEAP(name,0)=n-1
 D SIFTDOWN(name,1)
 Q 1

PEEK(name,key,payload)
 I +$G(^HHEAP(name,0),0)<1 S key="",payload="" Q 0
 S key=^HHEAP(name,1,1),payload=^HHEAP(name,2,1)
 Q 1

CLEAR(name)
 K ^HHEAP(name)
 Q

TEST
 N i,k,p,ok,bad,prev,cur
 S bad=0
 D CLEAR^HHEAP("t")
 S ok=$$POP^HHEAP("t",.k,.p)
 I ok W "FAIL pop empty",! S bad=bad+1
 D PUSH^HHEAP("t",5,"e")
 D PUSH^HHEAP("t",1,"a")
 D PUSH^HHEAP("t",3,"c")
 D PUSH^HHEAP("t",2,"b")
 D PUSH^HHEAP("t",4,"d")
 I $$HHEAPN^HHEAP("t")'=5 W "FAIL n=5",! S bad=bad+1
 S ok=$$PEEK^HHEAP("t",.k,.p)
 I ok=0!(k'=1)!(p'="a") W "FAIL peek min",! S bad=bad+1
 S prev=""
 F i=1:1:5 D
 . S ok=$$POP^HHEAP("t",.k,.p)
 . I ok=0 W "FAIL pop ",i,! S bad=bad+1 Q
 . I prev'="" S cur=+k I cur<(+prev) W "FAIL order ",i,! S bad=bad+1
 . S prev=k
 I $$HHEAPN^HHEAP("t")'=0 W "FAIL drain",! S bad=bad+1
 W "HHEAP TEST bad=",bad," n=",$$HHEAPN^HHEAP("t"),!
 Q
