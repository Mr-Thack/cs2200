lea $t0, STATEMENT
bgt $t0, $zero, PRINT
halt

PRINT:
lw $v0, 0($t0)
halt

STATEMENT: .fill 0x21212121
