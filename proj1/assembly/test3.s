lea $t0, TEST
lw $v0, 0($t0)
halt

TEST:
.fill 0x67676767
