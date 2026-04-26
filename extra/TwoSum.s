; 1. Two Sum

; Given an array of integers nums and an integer target, return indices of the
; two numbers such that they add up to target.

; You may assume that each input would have exactly one solution, and you may
; not use the same element twice.

; You can return the answer in any order.
; https://leetcode.com/problems/two-sum/description/


main:       
          add $s0, $zero, $zero       ! $s0 = i = 0
          lea $s1, nums               ! $s1 = &nums

loop:     add $s2, $s1, $s0           ! $s2 = &nums[i]
          lw $s2, 0($s2)              ! $s2 = nums[i]
          nand $s2, $s2, $s2          ! $s2 = -nums[i]
          addi $s2, $s2, 1            ! $s2 = -nums[i]

          lea $t0, target             ! $t0 = &target
          lw $t0, 0($t0)              ! $t0 = target
          add $a0, $t0, $s2           ! $a0 = target - nums[i]

          lea $at, contains           ! $v0 = prev.contains(target - nums[i])
          jalr $at, $ra

          addi $v0, $v0, -1
          beq $v0, $zero, found       ! if prev.contains(target - nums[i])

          lea $t0, prev
          lw $t0, 0($t0)              ! $t0 = &prev
          lea $t1, prevlen            ! $t1 = &prevlen
          lw $t1, 0($t1)              ! $t1 = prevlen
          add $t0, $t0, $t1           ! $t0 = &prev[prevlen]

          nand $s2, $s2, $s2          ! $s2 = nums[i]
          addi $s2, $s2, 1            ! $s2 = nums[i]
          sw $s2, 0($t0)              ! prev[prevlen] = nums[i]

          addi $t1, $t1, 1            ! $t1 = prevlen + 1
          lea $t0, prevlen            ! $t0 = &prevlen
          sw $t1, 0($t0)              ! prevlen = prevlen + 1

          addi $s0, $s0, 1            ! i++
          beq $zero, $zero, loop

found:    add $s1, $t0, $zero         ! $s1 = j
          halt

contains: 
          add $t0, $zero, $zero       ! i = 0
          lea $t1, prev
          lw $t1, 0($t1)              ! $t1 = &prev

check:    lea $t2, prevlen            ! $t2 = &prevlen
          lw $t2, 0($t2)              ! $t2 = prevlen
          beq $t0, $t2, retfalse      ! if i == prevlen, return false

          add $t2, $t1, $t0           ! $t2 = prev[i]
          lw $t2, 0($t2)              ! $t2 = prev[i]
          beq $t2, $a0, rettrue       ! return true

          addi $t0, $t0, 1            ! i++
          beq $zero, $zero, check     ! go back to check

rettrue:  addi $v0, $zero, 1          ! return true
          jalr $ra, $zero
retfalse: addi $v0, $zero, 0          ! return false
          jalr $ra, $zero

initsp:   .fill 0xa000
prev:     .fill 0xb000
prevlen:  .fill 0
len:      .fill 20
target:   .fill 25

nums:
          .fill 12      
          .fill 0xFFFFFFFC  
          .fill 19      
          .fill 7       
          .fill 50      
          .fill 0xFFFFFFE2     
          .fill 3       
          .fill 34      
          .fill 1       
          .fill 9       
          .fill 20      
          .fill 2       
          .fill 0xFFFFFFF5     
          .fill 41      
          .fill 0xFFFFFFF7      
          .fill 8       
          .fill 27      
          .fill 6       
          .fill 0xFFFFFFF1     
          .fill 5       
