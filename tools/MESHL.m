MESHL ; load the MESHX line-based export — Phase 4.1 load leg (ydb-mesh#58)
 ; Runs under GT.M (U04 scratch gld). Entry: mumps -run MESHL with env:
 ;   MESHLF = input .bin file (R/X tagged ref+val line pairs, see MESHX.m)
 N fn,rl,vl,ref,val,n
 S fn=$ZTRNLNM("MESHLF") I fn="" W "no MESHLF",! Q
 O fn
 U fn
 S n=0
LOOP R rl I $ZEOF G DONE
 R vl I $ZEOF G DONE
 S ref=$E(rl,2,$L(rl))
 I $E(rl,1)="X" S ref=$$UNHEX(ref)
 S val=$E(vl,2,$L(vl))
 I $E(vl,1)="X" S val=$$UNHEX(val)
 S @ref=val
 S n=n+1
 G LOOP
DONE C fn
 W "loaded=",n,!
 Q
UNHEX(h) ; decode hex string to bytes ($A-based digit decode; $F is off-by-one here)
 N i,a,b,v
 S v=""
 F i=1:2:$L(h) D
 . S a=$A($E(h,i)) S a=$S(a<58:a-48,1:a-55)
 . S b=$A($E(h,i+1)) S b=$S(b<58:b-48,1:b-55)
 . S v=v_$C(a*16+b)
 Q v
