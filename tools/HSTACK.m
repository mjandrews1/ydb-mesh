HSTACK ; LIFO stack over a global
 ;
 ; Schema:
 ;   ^HSTK(<name>,0)     = top index (0 = empty)
 ;   ^HSTK(<name>,1,<n>) = value at depth n (1 = bottom)
 ;
 ; API:
 ;   D PUSH^HSTACK(name,val)
 ;   S ok=$$POP^HSTACK(name,.val)   ; ok=1/0
 ;   S ok=$$PEEK^HSTACK(name,.val)  ; ok=1/0, does not pop
 ;   $$DEPTH^HSTACK(name)
 ;   D CLEAR^HSTACK(name)
 Q

DEPTH(name)
 Q +$G(^HSTK(name,0),0)

PUSH(name,val)
 N t
 S t=+$G(^HSTK(name,0),0)+1
 S ^HSTK(name,1,t)=val
 S ^HSTK(name,0)=t
 Q

POP(name,val)
 N t
 S t=+$G(^HSTK(name,0),0)
 I t<1 S val="" Q 0
 S val=^HSTK(name,1,t)
 K ^HSTK(name,1,t)
 S ^HSTK(name,0)=t-1
 Q 1

PEEK(name,val)
 N t
 S t=+$G(^HSTK(name,0),0)
 I t<1 S val="" Q 0
 S val=^HSTK(name,1,t)
 Q 1

CLEAR(name)
 K ^HSTK(name)
 Q

TEST
 N v,ok,bad,want
 S bad=0
 D CLEAR^HSTACK("t")
 I $$DEPTH^HSTACK("t")'=0 W "FAIL empty depth",! S bad=bad+1
 S ok=$$POP^HSTACK("t",.v)
 I ok W "FAIL pop empty",! S bad=bad+1
 D PUSH^HSTACK("t","a")
 D PUSH^HSTACK("t","b")
 D PUSH^HSTACK("t","c")
 I $$DEPTH^HSTACK("t")'=3 W "FAIL depth 3",! S bad=bad+1
 S ok=$$PEEK^HSTACK("t",.v)
 I ok=0!(v'="c") W "FAIL peek c",! S bad=bad+1
 I $$DEPTH^HSTACK("t")'=3 W "FAIL peek changed depth",! S bad=bad+1
 S want="c"
 S ok=$$POP^HSTACK("t",.v)
 I ok=0!(v'=want) W "FAIL pop c",! S bad=bad+1
 S want="b"
 S ok=$$POP^HSTACK("t",.v)
 I ok=0!(v'=want) W "FAIL pop b",! S bad=bad+1
 S want="a"
 S ok=$$POP^HSTACK("t",.v)
 I ok=0!(v'=want) W "FAIL pop a",! S bad=bad+1
 S ok=$$POP^HSTACK("t",.v)
 I ok W "FAIL pop empty after drain",! S bad=bad+1
 W "HSTACK TEST bad=",bad," depth=",$$DEPTH^HSTACK("t"),!
 Q
