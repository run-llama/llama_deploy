import reflex as rx

from frontend import style
from frontend.state import State
from frontend.session_list.component import session_list
from frontend.session_list.state import SessionState


def qa(content: str, idx: int) -> rx.Component:
    return rx.box(
        rx.text(content, style=style.answer_style),
        text_align=rx.cond(idx % 2 == 0, "right", "left"),
        margin_left="1em",
    )


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(State.chat_history, lambda messages, idx: qa(messages, idx))
    )


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            placeholder="Ask a question",
            on_change=State.set_question,
            on_key_down=lambda key: State.handle_key_down(
                key, SessionState.selected_session_id
            ),
            style=style.input_style,
        ),
        rx.button(
            "Ask",
            on_click=lambda: State.answer(SessionState.selected_session_id),
            style=style.button_style,
        ),
    )


def index() -> rx.Component:
    return rx.center(
        rx.hstack(
            session_list(),
            rx.vstack(
                chat(),
                action_bar(),
                align="center",
            ),
            margin_left="4",
        ),
    )


app = rx.App()
app.add_page(index, on_load=SessionState.create_default_session)
