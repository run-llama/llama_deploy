import reflex as rx

from .state import SessionState


def session_item(session: dict, index: int):
    return rx.cond(
        index == SessionState.editing_index,
        edit_mode(index),
        display_mode(session, index),
    )


def edit_mode(index: int):
    return rx.input(
        value=SessionState.edit_value,
        on_change=SessionState.set_edit_value,
        on_blur=lambda _: SessionState.save_edit(),
        on_key_down=SessionState.handle_key_press,
        auto_focus=True,
    )


def display_mode(session: dict, index: int):
    return rx.box(
        rx.text(
            session["session_name"],
            font_weight="medium",
        ),
        cursor="pointer",
        on_click=SessionState.select_session(index),
        padding="0.75em",
        border_radius="8px",
        background=rx.cond(
            index == SessionState.selected_session_index,
            "rgba(59, 130, 246, 0.1)",  # Light blue background for selected item
            "transparent",
        ),
        border_left=rx.cond(
            index == SessionState.selected_session_index,
            "4px solid rgb(59, 130, 246)",  # Blue left border for selected item
            "4px solid transparent",
        ),
        _hover={
            "background": rx.cond(
                index == SessionState.selected_session_index,
                "rgba(59, 130, 246, 0.1)",
                "rgba(0, 0, 0, 0.05)",
            )
        },
        transition="all 0.2s ease-in-out",
    )


def session_list():
    return rx.vstack(
        rx.heading("Sessions", size="lg"),
        rx.vstack(
            rx.foreach(SessionState.sessions, session_item),
            width="100%",
            spacing="4",
        ),
        # Add button at the bottom
        rx.button(
            "+",
            on_click=SessionState.add_session,
            margin_top="4",
            border_radius="25px",
        ),
        width="100%",
        max_width="600px",
        padding="4",
        spacing="4",
    )
