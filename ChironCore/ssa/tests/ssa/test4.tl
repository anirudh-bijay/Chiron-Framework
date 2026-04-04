:left = 0
:right = :x

repeat 10000 [
    :mid = (:left + :right) / 2
    if :mid * :mid == :x [
        :left = :mid
        :right = :mid
    ] else [
        if :mid * :mid < :x [
            :left = :mid + 1
        ] else [
            :right = :mid - 1
        ]
    ]
]