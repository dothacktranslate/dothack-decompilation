extern "C" float sqrtf(float);
extern "C" float atan2f(float, float);

int SetAnalogStick(float* angle, unsigned char* magnitude, int x, int y)
{
    int temp = x - 0x80;
    int adjusted_x;
    int adjusted_y;

    if (temp > 0x30) {
        adjusted_x = x - 0xB0;
    } else {
        adjusted_x = 0;

        if (temp < -0x30) {
            adjusted_x = x - 0x50;
        }
    }

    temp = y - 0x80;

    if (temp > 0x30) {
        adjusted_y = y - 0xB0;
    } else if (temp < -0x30) {
        adjusted_y = y - 0x50;
    } else {
        adjusted_y = 0;
    }

    int value = (int)(
        (255.0f *
         sqrtf((float)(
             adjusted_x * adjusted_x +
             adjusted_y * adjusted_y
         ))) /
        80.0f
    );

    if (value > 0xFF) {
        value = 0xFF;
    }

    if (value != 0) {
        int centered_y = y - 0x80;

        if (centered_y != 0) {
            float result = atan2f(
                (float)-(x - 0x80),
                (float)centered_y
            );

            if (result < -3.1415927f) {
                result = 6.2831855f + result;
            }

            *angle = result;
        } else {
            *angle = 0.0f;
        }

        *magnitude = (unsigned char)value;

        return 0;
    }

    *angle = 0.0f;
    *magnitude = 0;

    return 1;
}
