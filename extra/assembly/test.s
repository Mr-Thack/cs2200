!=============================================================================
! LC-5200b Comprehensive Pipeline & Instruction Test
!
! Register map (usable working registers):
!   $v0         — return value / scratch
!   $a0,$a1,$a2 — argument / scratch
!   $t0,$t1,$t2 — temporaries
!   $s0,$s1,$s2 — saved (we save/restore if we use them across calls)
!   $at         — branch/jump target address
!   $sp         — stack pointer (initialized in main)
!   $ra         — return address
!
! Failure protocol: every test ends with
!     beq  $result, $expected, PASS_label
!     halt                         ! FAIL — wrong result; halted PC identifies test
! PASS_label:
!
! A clean run reaches DONE at the very bottom.
!=============================================================================

main:
    lea  $sp, initsp
    lw   $sp, 0($sp)

!=============================================================================
! SECTION 1 — ADD basic correctness
!=============================================================================

; T01: 3 + 5 = 8
    addi $t0, $zero, 3
    addi $t1, $zero, 5
    add  $t2, $t0, $t1
    addi $a0, $zero, 8
    beq  $t2, $a0, T01_pass
    halt                        ! FAIL T01: add positive
T01_pass:

; T02: x + 0 = x
    addi $t0, $zero, 42
    add  $t1, $t0, $zero
    addi $t2, $zero, 42
    beq  $t1, $t2, T02_pass
    halt                        ! FAIL T02: add $zero operand
T02_pass:

; T03: add $zero,$zero,$zero is a nop; $zero must still read 0
    add  $zero, $zero, $zero
    beq  $zero, $zero, T03_pass
    halt                        ! FAIL T03: structural nop / $zero corrupted
T03_pass:

!=============================================================================
! SECTION 2 — ADDI correctness and sign extension
!=============================================================================

; T04: positive immediate
    addi $t0, $zero, 7
    addi $t1, $zero, 7
    beq  $t0, $t1, T04_pass
    halt                        ! FAIL T04: addi positive
T04_pass:

; T05: negative immediate sign-extends correctly (-1)
    addi $t0, $zero, -1
    addi $t1, $zero, 0
    addi $t1, $t1,  -1
    beq  $t0, $t1, T05_pass
    halt                        ! FAIL T05: addi sign extension (-1)
T05_pass:

; T06: negative immediate sign-extends correctly (-4)
    addi $t0, $zero, -4
    addi $t1, $zero, 4
    add  $t2, $t0, $t1          ! -4 + 4 should = 0
    beq  $t2, $zero, T06_pass
    halt                        ! FAIL T06: addi sign extension (-4)
T06_pass:

; T07: addi accumulate 0+1+1+1 = 3
    addi $t0, $zero, 0
    addi $t0, $t0, 1
    addi $t0, $t0, 1
    addi $t0, $t0, 1
    addi $t1, $zero, 3
    beq  $t0, $t1, T07_pass
    halt                        ! FAIL T07: addi accumulate
T07_pass:

!=============================================================================
! SECTION 3 — $zero REGISTER PROTECTION
! Writing to $zero must never corrupt it; it always reads back as 0.
!=============================================================================

; T08: attempt write via add
    addi $t0, $zero, 99
    add  $zero, $t0, $t0        ! attempt to write 198 into $zero
    beq  $zero, $zero, T08a_pass
    halt                        ! structurally unreachable
T08a_pass:
    addi $t1, $zero, 5
    addi $t2, $zero, 5
    beq  $t1, $t2, T08_pass
    halt                        ! FAIL T08: $zero corrupted by add
T08_pass:

; T09: attempt write via addi
    addi $zero, $zero, 77       ! attempt to write 77 into $zero
    addi $t0, $zero, 3
    addi $t1, $zero, 3
    beq  $t0, $t1, T09_pass
    halt                        ! FAIL T09: $zero corrupted by addi
T09_pass:

; T10: attempt write via lw
    lea  $t0, T10_data
    lw   $zero, 0($t0)          ! attempt to load into $zero
    addi $t1, $zero, 1
    addi $t2, $zero, 1
    beq  $t1, $t2, T10_pass
    halt                        ! FAIL T10: $zero corrupted by lw
T10_data: .fill 0xBEEF
T10_pass:

!=============================================================================
! SECTION 4 — BEQ taken / not-taken / target accuracy
!=============================================================================

; T11: taken branch
    addi $t0, $zero, 11
    addi $t1, $zero, 11
    beq  $t0, $t1, T11_pass
    halt                        ! FAIL T11: beq not taken when equal
T11_pass:

; T12: not-taken branch must not jump
    addi $t0, $zero, 3
    addi $t1, $zero, 4
    beq  $t0, $t1, T12_wrong
    addi $t2, $zero, 1
    addi $a0, $zero, 1
    beq  $t2, $a0, T12_pass
    halt
T12_wrong:
    halt                        ! FAIL T12: beq taken when operands unequal
T12_pass:

; T13: branch target accuracy — must land EXACTLY at label, not ±1
    addi $t0, $zero, 0
    beq  $zero, $zero, T13_target
    addi $t0, $t0, 1            ! must NOT execute
    addi $t0, $t0, 1            ! must NOT execute
T13_target:
    beq  $t0, $zero, T13_pass
    halt                        ! FAIL T13: beq landed at wrong target
T13_pass:

; T14: beq $zero,$zero is always-taken; verify with a sentinel
    addi $t0, $zero, 0
    beq  $zero, $zero, T14_taken
    addi $t0, $t0, 1            ! must NOT execute
T14_taken:
    beq  $t0, $zero, T14_pass
    halt                        ! FAIL T14: always-taken beq not taken
T14_pass:

!=============================================================================
! SECTION 5 — LEA address correctness
!=============================================================================

; T15: lea then lw loads the correct constant
    lea  $t0, T15_data
    lw   $t1, 0($t0)
    lea  $t2, T15_expected
    lw   $t2, 0($t2)
    beq  $t1, $t2, T15_pass
    halt                        ! FAIL T15: lea/lw address wrong
T15_data:     .fill 0xABCD
T15_expected: .fill 0xABCD
T15_pass:

; T16: lea of two distinct labels gives different addresses
    lea  $t0, T16_labelA
    lea  $t1, T16_labelB
    beq  $t0, $t1, T16_same     ! addresses must NOT be equal
    beq  $zero, $zero, T16_pass
T16_same:
    halt                        ! FAIL T16: two distinct labels have same address
T16_labelA: .fill 0
T16_labelB: .fill 0
T16_pass:

!=============================================================================
! SECTION 6 — LW / SW memory round-trips
!=============================================================================

; T17: basic sw/lw round-trip
    addi $t0, $zero, 0x1234
    lea  $t1, T17_slot
    sw   $t0, 0($t1)
    lw   $t2, 0($t1)
    beq  $t2, $t0, T17_pass
    halt                        ! FAIL T17: sw/lw round-trip
T17_slot: .fill 0
T17_pass:

; T18: sw/lw with positive non-zero offset
    addi $t0, $zero, 0x5678
    lea  $t1, T18_base
    sw   $t0, 1($t1)
    lw   $t2, 1($t1)
    beq  $t2, $t0, T18_pass
    halt                        ! FAIL T18: sw/lw with offset +1
T18_base: .fill 0
          .fill 0
T18_pass:

; T19: two independent sw's then two lw's — no aliasing
    addi $t0, $zero, 0x0AAA
    addi $t1, $zero, 0x0BBB
    lea  $a0, T19_base
    sw   $t0, 0($a0)
    sw   $t1, 1($a0)
    lw   $t2, 0($a0)
    lw   $a1, 1($a0)
    beq  $t2, $t0, T19a_pass
    halt                        ! FAIL T19a: first store corrupted
T19a_pass:
    beq  $a1, $t1, T19_pass
    halt                        ! FAIL T19b: second store corrupted
T19_base: .fill 0
          .fill 0
T19_pass:

!=============================================================================
! SECTION 7 — RAW DATA HAZARDS
!=============================================================================

; T20: RAW distance 1 (producer → immediate consumer)
;      Needs EX→EX forwarding or a pipeline stall.
    addi $t0, $zero, 6
    add  $t1, $t0, $t0          ! $t0 used 1 cycle after write — RAW-1
    addi $t2, $zero, 12
    beq  $t1, $t2, T20_pass
    halt                        ! FAIL T20: RAW distance-1 (add→add)
T20_pass:

; T21: RAW distance 1 via addi→add
    addi $s0, $zero, 10
    add  $s1, $s0, $s0          ! RAW-1 on $s0
    addi $s2, $zero, 20
    beq  $s1, $s2, T21_pass
    halt                        ! FAIL T21: RAW distance-1 (addi→add)
T21_pass:

; T22: RAW distance 2 (one filler between producer and consumer)
    addi $t0, $zero, 7
    add  $zero, $zero, $zero    ! filler (1 instruction gap)
    add  $t1, $t0, $t0          ! $t0 used 2 cycles after write — RAW-2
    addi $t2, $zero, 14
    beq  $t1, $t2, T22_pass
    halt                        ! FAIL T22: RAW distance-2
T22_pass:

; T23: RAW chain — each instruction depends on the one immediately before it
    addi $t0, $zero, 1          ! $t0 = 1
    add  $t1, $t0, $t0          ! $t1 = 2  (RAW-1 on $t0)
    add  $t2, $t1, $t1          ! $t2 = 4  (RAW-1 on $t1)
    add  $a0, $t2, $t2          ! $a0 = 8  (RAW-1 on $t2)
    add  $a1, $a0, $a0          ! $a1 = 16 (RAW-1 on $a0)
    addi $a2, $zero, 16
    beq  $a1, $a2, T23_pass
    halt                        ! FAIL T23: RAW dependency chain
T23_pass:

!=============================================================================
! SECTION 8 — LOAD-USE HAZARDS
!=============================================================================

; T24: lw → immediate use (hardest case; stall mandatory even with forwarding)
    lea  $t0, T24_data
    lw   $t1, 0($t0)            ! $t1 = 5
    add  $t2, $t1, $t1          ! load-use RAW; needs bubble
    addi $a0, $zero, 10
    beq  $t2, $a0, T24_pass
    halt                        ! FAIL T24: load-use (lw then immediate use)
T24_data: .fill 5
T24_pass:

; T25: lw → use with 1 filler (gap = 2; MEM→EX forward should work)
    lea  $t0, T25_data
    lw   $t1, 0($t0)            ! $t1 = 9
    add  $zero, $zero, $zero    ! 1 filler
    add  $t2, $t1, $t1          ! 2 cycles after lw
    addi $a0, $zero, 18
    beq  $t2, $a0, T25_pass
    halt                        ! FAIL T25: lw + 1 filler then use
T25_data: .fill 9
T25_pass:

; T26: lw result used as base address in the very next lw (double load-use)
    lea  $t0, T26_ptr_slot      ! $t0 = address of the pointer slot
    lea  $t1, T26_val           ! $t1 = address of T26_val (the thing we want to point at)
    sw   $t1, 0($t0)            ! store the pointer: mem[T26_ptr_slot] = &T26_val
    lw   $t1, 0($t0)            ! $t1 = address of T26_val (load the pointer)
    lw   $t2, 0($t1)            ! LOAD-USE: $t1 used immediately as base register
    addi $a0, $zero, 0x1111
    beq  $t2, $a0, T26_pass
    halt                        ! FAIL T26: load-use on base register of second lw
T26_val:  .fill 0x1111
T26_ptr_slot:  .fill 0         ! pointer to T26_val
T26_pass:

; T27: lw result used as base address in the very next sw
    lea  $t0, T27_ptr_slot      ! $t0 = address of the pointer slot
    lea  $t1, T27_slot          ! $t1 = address of T27_slot
    sw   $t1, 0($t0)            ! store the pointer: mem[T27_ptr_slot] = &T27_slot
    lw   $t1, 0($t0)            ! $t1 = address of T27_slot (load the pointer)
    sw   $zero, 0($t1)          ! LOAD-USE: $t1 used immediately as base for sw
    lw   $t2, 0($t1)            ! read back — should be 0
    beq  $t2, $zero, T27_pass
    halt                        ! FAIL T27: load-use on base register of sw
T27_slot: .fill 0xDEAD
T27_ptr_slot:  .fill 0
T27_pass:

!=============================================================================
! SECTION 9 — CONTROL HAZARDS: beq flush correctness
!=============================================================================

; T28: taken beq — instructions fetched after branch must NOT execute
    addi $t0, $zero, 0
    beq  $zero, $zero, T28_skip
    addi $t0, $t0, 1            ! must be flushed (fetched speculatively)
    addi $t0, $t0, 1            ! must be flushed
T28_skip:
    beq  $t0, $zero, T28_pass
    halt                        ! FAIL T28: post-beq instructions not flushed
T28_pass:

; T29: not-taken beq — fall-through instruction MUST execute
    addi $t0, $zero, 1
    addi $t1, $zero, 2
    beq  $t0, $t1, T29_wrong    ! not taken
    addi $t2, $zero, 7          ! must execute
    addi $a0, $zero, 7
    beq  $t2, $a0, T29_pass
    halt
T29_wrong:
    halt                        ! FAIL T29a: not-taken beq jumped
T29_pass:

; T30: RAW + control hazard combined
;      The beq operand is the result of the immediately preceding addi.
;      The branch must read the CORRECT (forwarded) value, not the stale one.
    addi $t0, $zero, 5
    addi $t0, $t0, 0            ! $t0 still 5; RAW-1 into beq
    addi $t1, $zero, 5
    beq  $t0, $t1, T30_pass     ! beq must see $t0 = 5, not stale
    halt                        ! FAIL T30: beq read stale value (RAW into branch)
T30_pass:

; T31: RAW-1 into beq — producer is add, not addi
    addi $t0, $zero, 3
    addi $t1, $zero, 4
    add  $t2, $t0, $t1          ! $t2 = 7, RAW-1 into the beq below
    addi $a0, $zero, 7
    beq  $t2, $a0, T31_pass     ! must see $t2 = 7
    halt                        ! FAIL T31: beq read stale value (add→beq RAW-1)
T31_pass:

; T32: back-to-back branches — second beq is fetched while first is resolving.
;      Both must resolve correctly with independent operands.
    addi $t0, $zero, 1
    addi $t1, $zero, 1
    addi $t2, $zero, 2
    beq  $t0, $t1, T32_first_taken   ! taken
    halt                             ! FAIL T32a: first beq not taken
T32_first_taken:
    addi $a0, $zero, 0
    beq  $t0, $t2, T32_second_wrong  ! NOT taken (1 != 2)
    beq  $zero, $zero, T32_pass
T32_second_wrong:
    halt                             ! FAIL T32b: second beq taken incorrectly
T32_pass:

; T33: branch to a target that is itself a branch (branch chain).
;      Flush from B1 must not corrupt decode of B2.
    addi $t0, $zero, 0
    beq  $zero, $zero, T33_B2       ! B1: taken, lands at B2
    addi $t0, $t0, 1                ! must be flushed by B1
T33_B2:
    addi $t1, $zero, 0
    beq  $zero, $zero, T33_B3       ! B2: also taken, lands at B3
    addi $t1, $t1, 1                ! must be flushed by B2
T33_B3:
    beq  $t0, $zero, T33_a_pass
    halt                            ! FAIL T33a: B1 flush let shadow instruction run
T33_a_pass:
    beq  $t1, $zero, T33_pass
    halt                            ! FAIL T33b: B2 flush let shadow instruction run
T33_pass:

; T34: tight beq loop — flush must happen correctly on EVERY iteration, not just the first.
;      Counts down from 4 to 0; on each iteration the back-edge branch is taken.
;      The instruction immediately after the branch must never execute.
    addi $t0, $zero, 4          ! loop counter
    addi $t1, $zero, 0          ! sentinel (must stay 0)
T34_loop:
    addi $t0, $t0, -1
    beq  $t0, $zero, T34_exit   ! exit when counter hits 0
    beq  $zero, $zero, T34_loop ! back-edge (taken each non-exit iteration)
    addi $t1, $t1, 1            ! must NEVER execute (shadow of back-edge branch)
T34_exit:
    beq  $t1, $zero, T34_pass
    halt                        ! FAIL T34: loop back-edge shadow instruction ran
T34_pass:

; T35: beq fall-through then beq taken in immediate succession — operand isolation.
;      Tests that the second beq doesn't inherit the stale PC offset of the first.
    addi $t0, $zero, 9
    addi $t1, $zero, 8
    beq  $t0, $t1, T35_wrong1  ! NOT taken (9 != 8); must fall through
    addi $t2, $zero, 9
    beq  $t0, $t2, T35_pass    ! taken (9 == 9)
T35_wrong1:
    halt                        ! FAIL T35a: first beq taken when should not be
    halt                        ! FAIL T35b: second beq not taken
T35_pass:

!=============================================================================
! SECTION 10 — JALR flush and link-register correctness
!=============================================================================

; T36: jalr saves PC+1 into $ra, jumps to correct target, returns cleanly
    addi $sp, $sp, -1
    sw   $ra, 0($sp)
    lea  $at, T36_func
    jalr $at, $ra
    addi $t0, $zero, 1          ! T36_return — must execute after return
    addi $a0, $zero, 1
    beq  $t0, $a0, T36_pass
    halt
T36_func:
    jalr $ra, $zero
T36_pass:
    lw $ra, 0($sp)
    addi $sp, $sp, 1
    
; T37: jalr flushes its own shadow instructions (1–2 fetched after jalr must not run)
    addi $t0, $zero, 0          ! sentinel
    lea  $at, T37_func
    jalr $at, $zero             ! jump
    addi $t0, $t0, 1            ! shadow 1 — must be flushed
    addi $t0, $t0, 1            ! shadow 2 — must be flushed
T37_func:
    beq  $t0, $zero, T37_pass
    halt                        ! FAIL T37: instructions after jalr were not flushed
T37_pass:

; T38: jalr with $zero as link destination — $zero must not be clobbered
    lea  $at, T38_func
    jalr $at, $zero             ! discard return address; $zero must stay 0
    beq  $zero, $zero, T38_after ! always-taken; lands here after return
    halt
T38_func:
    lea  $at, T38_ret
    jalr $at, $zero
    halt
T38_ret:
    beq  $zero, $zero, T38_back
    halt
T38_back:
T38_after:
    addi $t0, $zero, 0
    beq  $t0, $zero, T38_pass
    halt                        ! FAIL T38: $zero corrupted by jalr link write
T38_pass:

; T39: jalr return address is PC+1, not PC or PC+2.
;      We measure the gap by storing the jalr's own address and comparing to $ra.
    lea  $t0, T39_jalr          ! address of the jalr instruction itself

    addi $t0, $t0, 1            ! expected $ra = jalr address + 1
    lea  $at, T39_func

T39_jalr:
    jalr $at, $ra               ! $ra should equal T39_jalr_addr + 1

    addi $a0, $zero, 0          ! T39_return — this is where execution resumes
    beq  $ra, $t0, T39_pass     ! compare saved $ra to expected
    halt                        ! FAIL T39: jalr saved wrong return address

T39_func:
    add  $zero, $zero, $zero    ! Bubble to resolve RAW hazard on $ra
    add  $zero, $zero, $zero    ! Bubble
    add  $zero, $zero, $zero    ! Bubble
    jalr $ra, $zero
T39_pass:

; T40: jalr → beq immediately after return (return landing zone is a branch)
;      Tests that the return address is correct when the instruction at PC+1
;      (the return site) happens to also be a branch.
    addi $t0, $zero, 0
    lea  $at, T40_func
    jalr $at, $ra               ! call
    beq  $zero, $zero, T40_skip ! return lands HERE; this beq must execute and be taken
    halt
T40_skip:
    addi $t0, $t0, 1            ! must execute (landed via the beq above)
    addi $a0, $zero, 1
    beq  $t0, $a0, T40_pass
    halt                        ! FAIL T40: jalr return + immediate branch broken
T40_func:
    jalr $ra, $zero
T40_pass:

!=============================================================================
! SECTION 11 — WAW (write-after-write) hazard
!=============================================================================

; T41: second write to same register must win
    addi $t0, $zero, 5
    addi $t0, $zero, 9          ! WAW — second write
    addi $t1, $zero, 9
    beq  $t0, $t1, T41_pass
    halt                        ! FAIL T41: WAW — first write clobbered second
T41_pass:

; T42: WAW with add then addi, 1-cycle apart
    addi $t0, $zero, 3
    add  $t0, $t0, $t0          ! $t0 = 6; first write
    addi $t0, $zero, 99         ! $t0 = 99; second write (1 cycle after first)
    addi $t1, $zero, 99
    beq  $t0, $t1, T42_pass
    halt                        ! FAIL T42: WAW add→addi 1-cycle
T42_pass:

!=============================================================================
! SECTION 12 — WAR (write-after-read) hazard
!=============================================================================

; T43: reader must see old value; subsequent write must not affect reader's result
    addi $t0, $zero, 3
    add  $t1, $t0, $zero        ! read $t0 = 3 into $t1
    addi $t0, $zero, 99         ! write new value to $t0 (WAR)
    addi $t2, $zero, 3
    beq  $t1, $t2, T43_pass
    halt                        ! FAIL T43: WAR — reader got new value
T43_pass:

!=============================================================================
! SECTION 13 — STRUCTURAL HAZARD: back-to-back memory operations
!=============================================================================

; T44: three consecutive lw's — tests single-port memory stall logic
    lea  $t0, T44_data
    lw   $a0, 0($t0)
    lw   $a1, 1($t0)
    lw   $a2, 2($t0)
    addi $t1, $zero, 0x10
    addi $t2, $zero, 0x20
    addi $s0, $zero, 0x30
    beq  $a0, $t1, T44a_pass
    halt                        ! FAIL T44a: structural hazard corrupted lw 0
T44a_pass:
    beq  $a1, $t2, T44b_pass
    halt                        ! FAIL T44b: structural hazard corrupted lw 1
T44b_pass:
    beq  $a2, $s0, T44_pass
    halt                        ! FAIL T44c: structural hazard corrupted lw 2
T44_data:
    .fill 0x10
    .fill 0x20
    .fill 0x30

T44_pass:

; T45: interleaved sw and lw — store then immediately load from same address
    addi $t0, $zero, 0x4321
    lea  $t1, T45_slot
    sw   $t0, 0($t1)            ! MEM write cycle N
    lw   $t2, 0($t1)            ! MEM read cycle N+1 — may conflict on single-port
    beq  $t2, $t0, T45_pass
    halt                        ! FAIL T45: sw→lw same address structural conflict
T45_slot: .fill 0
T45_pass:

!=============================================================================
! SECTION 14 — COMBINED / STRESS: realistic calling convention
!=============================================================================

; T46: nested call — outer saves $ra, calls inner, inner returns $v0=42,
;      outer verifies $ra restored correctly and $v0 intact.
    addi $sp, $sp, -1
    sw   $ra, 0($sp)            ! save $ra

    lea  $at, T46_leaf
    jalr $at, $ra               ! call leaf

    lw   $ra, 0($sp)            ! restore $ra (load-use: $ra not used until return)
    addi $sp, $sp, 1

    addi $t0, $zero, 42
    beq  $v0, $t0, T46_pass
    halt                        ! FAIL T46: calling convention stress test
T46_leaf:
    addi $v0, $zero, 42
    jalr $ra, $zero
T46_pass:

; T47: s-register preservation — callee must not clobber $s0
    addi $s0, $zero, 0x7777     ! caller sets $s0
    addi $sp, $sp, -1
    sw   $ra, 0($sp)

    lea  $at, T47_callee
    jalr $at, $ra

    lw   $ra, 0($sp)
    addi $sp, $sp, 1

    addi $t0, $zero, 0x7777
    beq  $s0, $t0, T47_pass
    halt                        ! FAIL T47: callee clobbered $s0
T47_callee:
    addi $sp, $sp, -1           ! save $s0 per calling convention
    sw   $s0, 0($sp)
    addi $s0, $zero, 0xAAAA     ! use $s0 internally
    lw   $s0, 0($sp)            ! restore $s0
    addi $sp, $sp, 1
    jalr $ra, $zero
T47_pass:

!=============================================================================
! DONE — every test passed
!=============================================================================
DONE:
    halt

!=============================================================================
! Data section
!=============================================================================
initsp: .fill 0xA000
