#!/usr/bin/expect


spawn python simulator.py ../pow.bin

after 500

set timeout 0; # but wait in the while loop
set count 0

while {1} {
    send "s\r"
    incr count

    expect {
        -re "HALT" { break }
        default { }
    }
    
    after 10
}

puts "Number of s inputs: $count"
send "quit\r"
