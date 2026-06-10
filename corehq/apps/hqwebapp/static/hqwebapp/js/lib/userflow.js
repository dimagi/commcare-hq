import userflow from "userflow.js";
import initialPageData from "hqwebapp/js/initial_page_data";

const token = initialPageData.get("userflow_token");
const userId = initialPageData.get("userflow_user_id");
if (token && userId) {
    userflow.init(token);
    userflow.identify(userId, {
        signed_up_at: JSON.parse(initialPageData.get("userflow_signed_up_at")),
        server_env: initialPageData.get("userflow_server_env"),
        domain: initialPageData.get("userflow_domain"),
        subs_plan: initialPageData.get("userflow_subs_plan"),
    });
}

export default userflow;
