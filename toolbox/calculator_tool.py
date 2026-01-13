def calculator(expression: str) -> str:
    """
    Evaluate an arithmetic expression string and return the result as a string. Supports +, -, *, / and parentheses, with standard (true) division. Numbers can be integers or decimals (e.g., 3, 4.5, .75). Unary +/- is supported.

    Args:
        expression: The arithmetic expression to evaluate. It may contain digits, a decimal point '.', '+', '-', '*', '/', parentheses '(', ')', and optional spaces.

    Returns:
        A string representing the numeric result of the evaluated expression.
        The result may be an integer-like string (e.g., "7") or a floating-point string (e.g., "7.5").
    """

    def parse_number(s: str, i: int):
        # Parse a number starting at s[i]. Supports forms like:
        #  "123", "123.45", ".5", "0.5"
        n = len(s)
        j = i
        has_digit = False
        has_dot = False
        while j < n:
            ch = s[j]
            if ch.isdigit():
                has_digit = True
                j += 1
            elif ch == '.' and not has_dot:
                has_dot = True
                j += 1
            else:
                break
        if not has_digit:
            raise ValueError("Invalid number format")
        num_str = s[i:j]
        return float(num_str), j

    def tokenize(s: str):
        # Convert the input string into a list of tokens: numbers (float), operators, and parentheses.
        # Handles unary + and - by folding them into the subsequent number when possible,
        # or by transforming '-(expr)' into '0 - (expr)'.
        tokens = []
        i, n = 0, len(s)

        def prev_is_op_or_none():
            if not tokens:
                return True
            return tokens[-1] in ('+', '-', '*', '/', '(')

        while i < n:
            ch = s[i]
            if ch.isspace():
                i += 1
                continue

            if ch.isdigit() or ch == '.':
                # Parse a float literal
                num, j = parse_number(s, i)
                tokens.append(num)
                i = j
                continue

            if ch in '+-':
                # Check for unary +/-
                if prev_is_op_or_none():
                    # Look ahead: if next starts a number, fold sign into the number
                    j = i + 1
                    while j < n and s[j].isspace():
                        j += 1
                    if j < n and (s[j].isdigit() or s[j] == '.'):
                        num, k = parse_number(s, j)
                        tokens.append(num if ch == '+' else -num)
                        i = k
                        continue
                    elif j < n and s[j] == '(':
                        # Transform '-(expr)' into '0 - ( expr )'
                        if ch == '-':
                            tokens.append(0.0)
                            tokens.append('-')
                            i = j  # let loop handle '('
                            continue
                        else:
                            # '+(expr)' is a no-op, skip '+'
                            i = j
                            continue
                    else:
                        raise ValueError("Invalid unary operator position")
                # Binary +/-
                tokens.append(ch)
                i += 1
                continue

            if ch in '*/()':
                tokens.append(ch)
                i += 1
                continue

            raise ValueError(f"Invalid character in expression: '{ch}'")
        return tokens

    def to_rpn(tokens):
        # Shunting-yard algorithm: convert infix tokens to Reverse Polish Notation (RPN).
        output = []
        ops = []
        prec = {'+': 1, '-': 1, '*': 2, '/': 2}

        for tok in tokens:
            if isinstance(tok, (int, float)):
                output.append(float(tok))
            elif tok in ('+', '-', '*', '/'):
                while ops and ops[-1] in prec and prec[ops[-1]] >= prec[tok]:
                    output.append(ops.pop())
                ops.append(tok)
            elif tok == '(':
                ops.append(tok)
            elif tok == ')':
                while ops and ops[-1] != '(':
                    output.append(ops.pop())
                if not ops or ops[-1] != '(':
                    raise ValueError("Mismatched parentheses")
                ops.pop()
            else:
                raise ValueError("Unknown token")
        while ops:
            op = ops.pop()
            if op in ('(', ')'):
                raise ValueError("Mismatched parentheses")
            output.append(op)
        return output

    def eval_rpn(rpn):
        # Evaluate the RPN expression using a stack with float arithmetic.
        stack = []
        for tok in rpn:
            if isinstance(tok, (int, float)):
                stack.append(float(tok))
            else:
                if len(stack) < 2:
                    raise ValueError("Invalid expression")
                b = stack.pop()
                a = stack.pop()
                if tok == '+':
                    stack.append(a + b)
                elif tok == '-':
                    stack.append(a - b)
                elif tok == '*':
                    stack.append(a * b)
                elif tok == '/':
                    if b == 0:
                        raise ValueError("Division by zero")
                    stack.append(a / b)  # true division
                else:
                    raise ValueError("Unknown operator")
        if len(stack) != 1:
            raise ValueError("Invalid expression")
        return stack[0]

    def format_number(x: float) -> str:
        # Format the result to a concise string:
        # - If it's numerically an integer, drop the trailing .0
        # - Otherwise, use standard string conversion without scientific notation for typical sizes
        if x == int(x):
            return str(int(x))
        # Use repr-like precision but cleaner; strip trailing zeros
        s = f"{x:.15g}"
        return s

    tokens = tokenize(expression)
    rpn = to_rpn(tokens)
    result = eval_rpn(rpn)
    return format_number(result)


if __name__ == '__main__':
    print(calculator("1+2"))  
    print(calculator("1+2*3"))    
    print(calculator("(1+2)*3"))  
    print(calculator("(1+2)/3"))  
    print(calculator("1/2"))   
    print(calculator("-.5 * 8")) 
    print(calculator("2*(3.5+0.5)"))
    print(calculator("1+3/4+3.4"))
