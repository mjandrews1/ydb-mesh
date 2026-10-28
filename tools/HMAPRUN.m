HMAPRUN
 ZLINK "HMAP"
 W "TEST begin",!
 D TEST^HMAP
 W "HASH alpha=",$$HASH^HMAP("alpha"),!
 W "HASH beta=",$$HASH^HMAP("beta"),!
 W "BUCKET alpha/1024=",$$BUCKET^HMAP("alpha",1024),!
 W "BUCKET beta/1024=",$$BUCKET^HMAP("beta",1024),!
 D PUT^HMAP("c","k","v1")
 S ok=$$GET^HMAP("c","k",.v)
 W "get ok=",ok," val=[",v,"]",!
 D DEL^HMAP("c","k")
 S ok=$$GET^HMAP("c","k",.v)
 W "after del ok=",ok," val=[",v,"]",!
 D PUT^HMAP("c","k","v2")
 S ok=$$GET^HMAP("c","k",.v)
 W "reinsert ok=",ok," val=[",v,"]",!
 D CLEAR^HMAP("col")
 S ^HM("col",4)=8
 F i=1:1:12 D PUT^HMAP("col","key"_i,"val"_i)
 W "collide count=",+$G(^HM("col",0)),!
 F i=1:1:12 S ok=$$GET^HMAP("col","key"_i,.v),want="val"_i I ok=0!(v'=want) W "FAIL ",i,!
 W "HMAPRUN DONE",!
 Q
