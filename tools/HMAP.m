HMAP ; hash map over globals — insert / lookup / delete / collisions
 ;
 ; Schema (one map per logical name):
 ;   ^HM(<name>,0)            = insert count
 ;   ^HM(<name>,1,<bucket>)   = chain length
 ;   ^HM(<name>,2,<key>)      = value
 ;   ^HM(<name>,3,<bucket>,<key>) = 1   (chain membership; separate chaining)
 ;
 ; Keys and values are strings (numeric strings stored as text).
 ; Hash is portable ISO M (no $ZHASH): 31-bit polynomial rolling hash.
 ;
 ; API (all args are strings):
 ;   D PUT^HMAP(name,key,val)     insert or overwrite
 ;   S ok=$$GET^HMAP(name,key,.v) lookup; ok=1/0, v=value or ""
 ;   D GETV^HMAP(name,key,.v)     DO-style lookup (sets v)
 ;   D DEL^HMAP(name,key)         delete (no-op if absent)
 ;   D CLEAR^HMAP(name)           drop the whole map
 ;   $$BUCKET^HMAP(key,nb)        bucket index 0..nb-1
 ;   $$HASH^HMAP(key)             raw 31-bit hash
 ;
 ; Default bucket count is 1024 (overridable via ^HM(name,4)).
 Q

BUCKETS(name)
 Q +$G(^HM(name,4),1024)

HASH(key)
 ; Polynomial rolling hash, stays in 31-bit non-negative range (no overflow).
 N h,i
 S h=0
 F i=1:1:$L(key) S h=(h*31+$A(key,i))#2147483647
 Q h

XOR(a,b)
 ; portable non-negative integer xor (no $Z* dependency)
 N x,y,r,p
 S x=a,y=b,r=0,p=1
 F  Q:'(x+y)  S r=r+((x#2)'=(y#2))*p,x=x\2,y=y\2,p=p*2
 Q r


BUCKET(key,nb)
 I nb'>0 S nb=1024
 Q $$HASH(key)#nb

PUT(name,key,val)
 N b,nb
 S nb=$$BUCKETS(name)
 S b=$$BUCKET(key,nb)
 I '$D(^HM(name,3,b,key)) D
 . S ^HM(name,3,b,key)=1
 . S ^HM(name,1,b)=+$G(^HM(name,1,b))+1
 . S ^HM(name,0)=+$G(^HM(name,0))+1
 S ^HM(name,2,key)=val
 Q

GET(name,key,val)
 ; extrinsic: $$GET^HMAP(name,key,.val) -> 1/0
 N b,nb
 S nb=$$BUCKETS(name)
 S b=$$BUCKET(key,nb)
 I '$D(^HM(name,2,key)) S val="" Q 0
 S val=^HM(name,2,key)
 Q 1

GETV(name,key,val)
 ; DO-style wrapper (sets val, no return value)
 N ok
 S ok=$$GET^HMAP(name,key,.val)
 Q

DEL(name,key)
 N b,nb
 S nb=$$BUCKETS(name)
 S b=$$BUCKET(key,nb)
 I '$D(^HM(name,2,key)) Q
 K ^HM(name,2,key)
 I $D(^HM(name,3,b,key)) K ^HM(name,3,b,key) S ^HM(name,1,b)=+$G(^HM(name,1,b))-1
 S ^HM(name,0)=+$G(^HM(name,0))-1
 Q

CLEAR(name)
 K ^HM(name)
 Q

; ---- optional M-level smoke (D TEST^HMAP) ----
TEST
 N i,want,v,r,bad
 S bad=0
 D CLEAR^HMAP("t")
 F i=1:1:200 D PUT^HMAP("t","k"_i,"v"_i)
 F i=1:1:200 D
 . S r=$$GET^HMAP("t","k"_i,.v)
 . S want="v"_i
 . I r=0!(v'=want) W "FAIL get k",i,! S bad=bad+1
 D DEL^HMAP("t","k10")
 S r=$$GET^HMAP("t","k10",.v)
 I r W "FAIL del k10 still present",! S bad=bad+1
 D PUT^HMAP("t","k10","v10b")
 S r=$$GET^HMAP("t","k10",.v)
 I r=0!(v'="v10b") W "FAIL reinsert k10",! S bad=bad+1
 W "HMAP TEST bad=",bad," count=",+$G(^HM("t",0)),!
 Q
