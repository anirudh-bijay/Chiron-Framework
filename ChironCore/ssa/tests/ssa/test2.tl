:n = 1
:a = -50
repeat 100 [
    if (:n * 3 == 63 || :n * 6 == 36) [
        forward 100
        right 90
        :a = 17
    ] else [
        if (:n * 3 == 64 || (:n * 7 == 49 && :n + 1 != 8)) [
            backward 100
            left 90
            :a = :a + :n + :a
        ]
    ]
]

goto (:a, :a)