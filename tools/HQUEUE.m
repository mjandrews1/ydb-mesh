HQUEUE ; FIFO queue over a global (head/tail ring)
 ;
 ; Schema:
 ;   ^HQUE(<name>,0)     = count
 ;   ^HQUE(<name>,1)     = head slot (oldest)
 ;   ^HQUE(<name>,2)     = tail slot (next free)
 ;   ^HQUE(<name>,3,<i>) = value at slot i
 ;
 ; Slots advance monotonically; CLEAR resets counters. Fine for
 ; long-lived service queues (absolute slots, no wrap).
 ;
 ; API:
 ;   D ENQ^HQUEUE(name,val)
 ;   S ok=$$DEQ^HQUEUE(name,.val)   ; ok=1/0
 ;   S ok=$$FRONT^HQUEUE(name,.val) ; ok=1/0, does not dequeue
 ;   $$QCOUNT^HQUEUE(name)
 ;   D CLEAR^HQUEUE(name)
 Q

QCOUNT(name)
 Q +$G(^HQUE(name,0),0)

ENQ(name,val)
 N t
 S t=+$G(^HQUE(name,2),1)
 S ^HQUE(name,3,t)=val
 S ^HQUE(name,2)=t+1
 I '$G(^HQUE(name,1)) S ^HQUE(name,1)=t
 S ^HQUE(name,0)=+$G(^HQUE(name,0),0)+1
 Q

DEQ(name,val)
 N h,c
 S c=+$G(^HQUE(name,0),0)
 I c<1 S val="" Q 0
 S h=+$G(^HQUE(name,1),1)
 S val=^HQUE(name,3,h)
 K ^HQUE(name,3,h)
 S ^HQUE(name,1)=h+1
 S ^HQUE(name,0)=c-1
 I c-1<1 S ^HQUE(name,1)=+$G(^HQUE(name,2))
 Q 1

FRONT(name,val)
 N h,c
 S c=+$G(^HQUE(name,0),0)
 I c<1 S val="" Q 0
 S h=+$G(^HQUE(name,1),1)
 S val=^HQUE(name,3,h)
 Q 1

CLEAR(name)
 K ^HQUE(name)
 Q

TEST
 N v,ok,bad,want
 S bad=0
 D CLEAR^HQUEUE("t")
 I $$QCOUNT^HQUEUE("t")'=0 W "FAIL empty count",! S bad=bad+1
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok W "FAIL deq empty",! S bad=bad+1
 D ENQ^HQUEUE("t","a")
 D ENQ^HQUEUE("t","b")
 D ENQ^HQUEUE("t","c")
 I $$QCOUNT^HQUEUE("t")'=3 W "FAIL count 3",! S bad=bad+1
 S ok=$$FRONT^HQUEUE("t",.v)
 I ok=0!(v'="a") W "FAIL front a",! S bad=bad+1
 I $$QCOUNT^HQUEUE("t")'=3 W "FAIL front changed count",! S bad=bad+1
 S want="a"
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok=0!(v'=want) W "FAIL deq a",! S bad=bad+1
 S want="b"
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok=0!(v'=want) W "FAIL deq b",! S bad=bad+1
 D ENQ^HQUEUE("t","d")
 S want="c"
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok=0!(v'=want) W "FAIL deq c",! S bad=bad+1
 S want="d"
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok=0!(v'=want) W "FAIL deq d",! S bad=bad+1
 S ok=$$DEQ^HQUEUE("t",.v)
 I ok W "FAIL deq empty after drain",! S bad=bad+1
 W "HQUEUE TEST bad=",bad," count=",$$QCOUNT^HQUEUE("t"),!
 Q
