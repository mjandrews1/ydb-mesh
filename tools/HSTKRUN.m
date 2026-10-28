HSTKRUN
 ZLINK "HSTACK"
 ZLINK "HQUEUE"
 W "HSTACK begin",!
 D TEST^HSTACK
 W "HQUEUE begin",!
 D TEST^HQUEUE
 ; order demo
 D CLEAR^HSTACK("s")
 D PUSH^HSTACK("s","x1")
 D PUSH^HSTACK("s","x2")
 D PUSH^HSTACK("s","x3")
 S ok=$$POP^HSTACK("s",.a),ok2=$$POP^HSTACK("s",.b),ok3=$$POP^HSTACK("s",.c)
 W "stack pop order=",a,",",b,",",c," (LIFO)",!
 D CLEAR^HQUEUE("q")
 D ENQ^HQUEUE("q","x1")
 D ENQ^HQUEUE("q","x2")
 D ENQ^HQUEUE("q","x3")
 S ok=$$DEQ^HQUEUE("q",.a),ok2=$$DEQ^HQUEUE("q",.b),ok3=$$DEQ^HQUEUE("q",.c)
 W "queue deq order=",a,",",b,",",c," (FIFO)",!
 W "HSTKRUN DONE",!
 Q
