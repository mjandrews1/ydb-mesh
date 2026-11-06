MESHX ; global export, line-based binary-safe format — Phase 4.1 export leg (ydb-mesh#58)
 ; Runs under YottaDB (U02) against the restored scratch DB. Entry: mumps -run MESHX
 ; env: MESHXGL  = comma list of global names WITHOUT ^ (default: mesh set)
 ;      MESHXDIR = output dir with trailing / (default /home/mark/export-4.1/)
 ; Format (default VARIABLE record mode, identical on YDB and GT.M):
 ;   per node, TWO LF-terminated records:
 ;     ref line:  "R"_ref  or  "X"_hex(ref)   (X form when ref contains LF/NUL)
 ;     val line:  "R"_val  or  "X"_hex(val)   (X form when val contains LF/NUL)
 ; Only LF (the record terminator) and NUL need the hex slow path; it is rare.
 N gl,gi,g,dir,fn,pre,r,n
 S gl=$ZTRNLNM("MESHXGL")
 I gl="" S gl="MESH,MESHSTAT,GRAPH,GRAPHREV,PTERM,PTERMSTAT,PUBMED,PUBMEDSTAT,PREPRINT,PREPRINTSTAT,MARCSTAT,VARSTAT"
 S dir=$ZTRNLNM("MESHXDIR") I dir="" S dir="/home/mark/export-4.1/"
 F gi=1:1:$L(gl,",") D
 . S g=$P(gl,",",gi) Q:g=""
 . S fn=dir_g_".bin"
 . O fn
 . U fn
 . S n=0
 . I $D(@("^"_g)) D WREC("^"_g,$G(@("^"_g)))
 . S pre="^"_g_"("
 . S r="^"_g
 . F  S r=$Q(@r) Q:r=""  Q:$E(r,1,$L(pre))'=pre  D WREC(r,@r)
 . C fn
 . W g,"=",n,!
 Q
WREC(r,v) ; one node = two tagged records; n is the caller's counter
 I ($F(r,$C(10))>0)!($F(r,$C(0))>0)!($F(v,$C(10))>0)!($F(v,$C(0))>0) D HEXW(r,v)
 E  D RAWW(r,v)
 S n=n+1
 Q
HEXW(r,v)
 W "X",$$HEX(r),!
 W "X",$$HEX(v),!
 Q
RAWW(r,v)
 W "R",r,!
 W "R",v,!
 Q
HEX(s) ; hex-encode every byte of s
 N i,c,h
 S h=""
 F i=1:1:$L(s) S c=$A(s,i) S h=h_$E("0123456789ABCDEF",c\16+1)_$E("0123456789ABCDEF",(c#16)+1)
 Q h
