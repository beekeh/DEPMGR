"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import reflex as rx
import os
# from .cloud_api_state import CloudAPI as State
# from .dummy_state import Dummy as State
from .tf_state import Terraform as State

alerts: dict = {
    "check_status": "Click 'Check Status' to get the status.",
    "five_minutes": "It can take upto 5 minuites for the deployment to be ready."
}


@rx.page(on_load=State.initial_ui)
def index() -> rx.Component:

    def code_box_element(key, value) -> rx.Component:
        snippet = f"{key} = {value}"
        return (rx.hstack(
                rx.box(rx.code(snippet, font_size="0.7em")),
                rx.tooltip(
                rx.icon(
                    tag="copy", 
                    on_click=rx.set_clipboard(value),
                    position="right",
                    _hover={"color": "gray"},
                    _focus={"color": "primary"},),
                    label="Copy to clipboard",
            ))
        )
    
    creds_card = rx.card(
        rx.vstack(
            code_box_element(
                "url", State.url
            ),
            code_box_element(
                "username", State.username
            ),
            code_box_element(
                "password", State.password
                )
    ))
    return rx.fragment(
        rx.color_mode_button(rx.color_mode_icon(), float="right"),
        rx.vstack(
            rx.heading("DEPLOYMENT REQUEST", 
                       font_size="1.5em", 
                       font_weight="thin"),
            rx.cond((State.dep_state != State.dep_states[2]),
                rx.button(
                    State.cbutton_text,
                    color_scheme="teal",
                    on_click=State.start_deployment,
                    is_disabled=State.cbutton_disabled),
                rx.button(
                    State.tbutton_text,
                    color_scheme="pink",
                    on_click=State.shutdown_deploy,
                    is_disabled=State.tbutton_disabled),
                ),
            spacing="1.5em",
            font_size="2em",
            padding_top="4%",
            padding_bottom="1%",
        ),
        rx.cond(
            (State.dep_state == State.dep_states[2]), 
            rx.vstack(
            rx.alert(
                rx.alert_icon(), 
                rx.alert_title("Deployed"),
                status="success"),
            creds_card),
            rx.span("")),
        rx.cond((State.dep_state == State.dep_states[0]),
            rx.alert(
                rx.alert_icon(), 
                rx.alert_title("No Active Deployments", font_size="0.8em"),
                status="info"),
            rx.span("")),
        rx.cond((State.dep_state == State.dep_states[1]),
                rx.vstack(
                rx.alert(
                rx.alert_icon(), 
                rx.alert_title("Deployment Requested.", font_size="0.8em"),
                rx.alert_description(alerts["five_minutes"], font_size="0.8em"),
                status="warning"),
                rx.card(
                    rx.vstack(
                        rx.cond(
                            State.dep_state == State.dep_states[2], 
                            rx.vstack(
                                rx.circular_progress(value=100),
                                rx.code("Deployment Ready", font_size="0.7em")
                            ),
                            rx.span("")
                        ),
                        rx.cond(
                            State.dep_state == State.dep_states[1],
                            rx.vstack(
                                rx.circular_progress(is_indeterminate=True),
                                rx.code("Still Cooking...", font_size="0.7em")
                            ),
                            rx.span("")
                            )
                        )
                    ),
                ),
                rx.span("")
            )  
        )

# Add CloudAPI and page to the app.
if not os.environ.get("EC_API_KEY"):
    print("Please set an EC_API_KEY environment variable.")
    exit(1)
else:
    app = rx.App()
    app.add_page(index)
    app.compile()