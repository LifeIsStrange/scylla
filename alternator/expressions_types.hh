/*
 * Copyright 2019 ScyllaDB
 */

/*
 * This file is part of Scylla.
 *
 * See the LICENSE.PROPRIETARY file in the top-level directory for licensing information.
 */

#pragma once

#include <vector>
#include <string>
#include <variant>

/*
 * Parsed representation of expressions and their components.
 *
 * Types in alternator::parse namespace are used for holding the parse
 * tree - objects generated by the Antlr rules after parsing an expression.
 * Because of the way Antlr works, all these objects are default-constructed
 * first, and then assigned when the rule is completed, so all these types
 * have only default constructors - but setter functions to set them later.
 */

namespace alternator {
namespace parsed {

// "path" is an attribute's path in a document, e.g., a.b[3].c.
class path {
    // All paths have a "root", a top-level attribute, and any number of
    // "dereference operators" - each either an index (e.g., "[2]") or a
    // dot (e.g., ".xyz").
    std::string _root;
    std::vector<std::variant<std::string, unsigned>> _operators;
public:
    void set_root(std::string root) {
        _root = std::move(root);
    }
    void add_index(unsigned i) {
        _operators.emplace_back(i);
    }
    void add_dot(std::string(name)) {
        _operators.emplace_back(std::move(name));
    }
    const std::string& root() const {
        return _root;
    }
    bool has_operators() const {
        return !_operators.empty();
    }
};

// "value" is is a value used in the right hand side of an assignment
// expression, "SET a = ...". It can be a reference to a value included in
// the request (":val"), a path to an attribute from the existing item
// (e.g., "a.b[3].c"), or a function of other such values.
// Note that the real right-hand-side of an assignment is actually a bit
// more general - it allows either a value, or a value+value or value-value -
// see class set_rhs below.
class value {
public:
    struct function_call {
        std::string _function_name;
        std::vector<value> _parameters;
    };
private:
    std::variant<std::string, path, function_call> _value;
public:
    void set_valref(std::string s) {
        _value = std::move(s);
    }
    void set_path(path p) {
        _value = std::move(p);
    }
    void set_func_name(std::string s) {
        _value = function_call {std::move(s), {}};
    }
    void add_func_parameter(value v) {
        std::get<function_call>(_value)._parameters.emplace_back(std::move(v));
    }
    bool is_valref() const {
        return std::holds_alternative<std::string>(_value);
    }
    bool is_function_call() const {
        return std::holds_alternative<function_call>(_value);
    }
    bool is_path() const {
        return std::holds_alternative<path>(_value);
    }
    const std::string& as_valref() const {
        return std::get<std::string>(_value);
    }
    const function_call& as_function_call() const {
        return std::get<function_call>(_value);
    }
    const path& as_path() const {
        return std::get<path>(_value);
    }
};

// The right-hand-side of a SET in an update expression can be either a
// single value (see above), or value+value, or value-value.
class set_rhs {
public:
    char _op;  // '+', '-', or 'v''
    value _v1;
    value _v2;
    void set_value(value&& v1) {
        _op = 'v';
        _v1 = std::move(v1);
    }
    void set_plus(value&& v2) {
        _op = '+';
        _v2 = std::move(v2);
    }
    void set_minus(value&& v2) {
        _op = '-';
        _v2 = std::move(v2);
    }
};

class update_expression {
public:
    struct action {
        path _path;
        struct set {
            set_rhs _rhs;
        };
        struct remove {
        };
        struct add {
            std::string _valref;
        };
        struct del {
            std::string _valref;
        };
        std::variant<set, remove, add, del> _action;

        // FIXME: rhs type, not just one value, also value+value, value-value
        void assign_set(path p, set_rhs rhs) {
            _path = std::move(p);
            _action = set { std::move(rhs) };
        }
        void assign_remove(path p) {
            _path = std::move(p);
            _action = remove { };
        }
        void assign_add(path p, std::string v) {
            _path = std::move(p);
            _action = add { std::move(v) };
        }
        void assign_del(path p, std::string v) {
            _path = std::move(p);
            _action = del { std::move(v) };
        }
        bool is_set() const {
            return std::holds_alternative<set>(_action);
        }
        bool is_remove() const {
            return std::holds_alternative<remove>(_action);
        }
        bool is_add() const {
            return std::holds_alternative<add>(_action);
        }
        bool is_del() const {
            return std::holds_alternative<del>(_action);
        }
        const set& as_set() const {
            return std::get<set>(_action);
        }
        const remove& as_remove() const {
            return std::get<remove>(_action);
        }
        const add& as_add() const {
            return std::get<add>(_action);
        }
        const del& as_del() const {
            return std::get<del>(_action);
        }
    };
private:
    std::vector<action> _actions;
    bool seen_set = false;
    bool seen_remove = false;
    bool seen_add = false;
    bool seen_del = false;
public:
    void add(action a);
    void append(update_expression other);
    bool empty() const {
        return _actions.empty();
    }
    const std::vector<action>& actions() const {
        return _actions;
    }
};

} // namespace parsed
} // namespace alternator