repeat 90 [
    :side = 400

    repeat 2 [
        repeat 3 [
            forward :side
            left 120
        ]
        
        :side = :side / 2
        left 2
    ]
]