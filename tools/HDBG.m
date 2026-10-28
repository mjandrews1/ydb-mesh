HDBG
 ZLINK "HMAP"
 D CLEAR^HMAP("d")
 D PUT^HMAP("d","k1","v1")
 W "D0=",$G(^HM("d",0)),!
 W "D2k1=",+$D(^HM("d",2,"k1"))," val=",$G(^HM("d",2,"k1")),!
 S ok=$$GET^HMAP("d","k1",.v)
 W "ok=",ok," v=[",v,"]",!
 S r=$$GET^HMAP("d","k1",.v2)
 W "r=",r," v2=[",v2,"]",!
 ZWRITE ^HM("d")
 Q
